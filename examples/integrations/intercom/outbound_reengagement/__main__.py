import guava
import os
import logging
import argparse
import requests
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)

INTERCOM_ACCESS_TOKEN = os.environ["INTERCOM_ACCESS_TOKEN"]

BASE_URL = "https://api.intercom.io"
HEADERS = {
    "Authorization": f"Bearer {INTERCOM_ACCESS_TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Intercom-Version": "2.10",
}


def get_contact(contact_id: str) -> dict | None:
    resp = requests.get(f"{BASE_URL}/contacts/{contact_id}", headers=HEADERS, timeout=10)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def tag_contact(contact_id: str, tag_name: str) -> None:
    tag_resp = requests.post(f"{BASE_URL}/tags", headers=HEADERS, json={"name": tag_name}, timeout=10)
    tag_resp.raise_for_status()
    tag_id = tag_resp.json()["id"]
    requests.post(
        f"{BASE_URL}/contacts/{contact_id}/tags",
        headers=HEADERS,
        json={"id": tag_id},
        timeout=10,
    ).raise_for_status()


def update_contact(contact_id: str, updates: dict) -> None:
    requests.put(
        f"{BASE_URL}/contacts/{contact_id}",
        headers=HEADERS,
        json=updates,
        timeout=10,
    ).raise_for_status()


def create_conversation_note(contact_id: str, note: str) -> None:
    """Creates an Intercom conversation initiated as a note from the admin for context."""
    requests.post(
        f"{BASE_URL}/conversations",
        headers=HEADERS,
        json={
            "from": {"type": "contact", "id": contact_id},
            "body": note,
        },
        timeout=10,
    ).raise_for_status()


OUTCOME_TAGS = {
    "interested in returning": "re-engaged",
    "needs pricing info": "pricing-requested",
    "wants a demo": "demo-requested",
    "churned permanently": "churned-confirmed",
    "not interested": "not-interested",
}


class OutboundReengagementController(guava.CallController):
    def __init__(self, contact_id: str, contact_name: str):
        super().__init__()
        self.contact_id = contact_id
        self.contact_name = contact_name
        self.contact_email = ""
        self.last_seen = ""

        try:
            contact = get_contact(contact_id)
            if contact:
                self.contact_email = contact.get("email") or ""
                last_ts = contact.get("last_seen_at")
                if last_ts:
                    self.last_seen = datetime.utcfromtimestamp(last_ts).strftime("%B %Y")
        except Exception as e:
            logging.error("Failed to fetch contact %s pre-call: %s", contact_id, e)

        self.set_persona(
            organization_name="Stackline",
            agent_name="Casey",
            agent_purpose=(
                "to re-engage lapsed Stackline customers, understand why they stopped using "
                "the product, and explore whether there's a path to bringing them back"
            ),
        )

        self.reach_person(
            contact_full_name=contact_name,
            on_success=self.begin_reengagement,
            on_failure=self.recipient_unavailable,
        )

    def begin_reengagement(self):
        last_seen_note = f" We noticed you haven't been active since {self.last_seen}." if self.last_seen else ""

        self.set_task(
            objective=(
                f"Re-engage {self.contact_name} who has been inactive on Stackline. "
                "Understand their experience, whether they moved to a competitor, and whether "
                "there's any opportunity to bring them back."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.contact_name}, this is Casey from Stackline.{last_seen_note} "
                    "I'm calling because we value your business and wanted to check in personally."
                ),
                guava.Field(
                    key="still_using",
                    field_type="multiple_choice",
                    description=(
                        "Ask if they're still using Stackline or if they've moved on."
                    ),
                    choices=["still using it", "haven't used it in a while", "switched to another tool"],
                    required=True,
                ),
                guava.Field(
                    key="reason_for_lapse",
                    field_type="text",
                    description=(
                        "Ask what caused them to step away or reduce usage. "
                        "Be empathetic and non-pressuring. Capture their honest response."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="reengagement_interest",
                    field_type="multiple_choice",
                    description=(
                        "Based on the conversation, assess their interest in returning or re-engaging."
                    ),
                    choices=[
                        "interested in returning",
                        "needs pricing info",
                        "wants a demo",
                        "churned permanently",
                        "not interested",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="missing_feature",
                    field_type="text",
                    description=(
                        "Ask: 'Is there anything specific we could offer or improve that would "
                        "make Stackline the right fit for you?' Capture their answer."
                    ),
                    required=False,
                ),
            ],
            on_complete=self.record_outcome,
        )

    def record_outcome(self):
        still_using = self.get_field("still_using") or "haven't used it in a while"
        reason = self.get_field("reason_for_lapse") or ""
        interest = self.get_field("reengagement_interest") or "not interested"
        missing = self.get_field("missing_feature") or ""

        tag = OUTCOME_TAGS.get(interest, "contacted")

        logging.info(
            "Re-engagement call complete for %s — interest: %s", self.contact_name, interest,
        )

        try:
            tag_contact(self.contact_id, tag)
            tag_contact(self.contact_id, "reengagement-called")
            logging.info("Tags applied to contact %s.", self.contact_id)
        except Exception as e:
            logging.error("Failed to tag contact %s: %s", self.contact_id, e)

        custom_attrs = {
            "reengagement_outcome": interest,
            "reengagement_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        }
        try:
            update_contact(self.contact_id, {"custom_attributes": custom_attrs})
            logging.info("Contact %s updated with reengagement outcome.", self.contact_id)
        except Exception as e:
            logging.error("Failed to update contact %s: %s", self.contact_id, e)

        if interest in ("interested in returning", "needs pricing info", "wants a demo"):
            self.hangup(
                final_instructions=(
                    f"Express genuine excitement about reconnecting with {self.contact_name}. "
                    + ("Let them know the sales team will reach out with updated pricing within one business day. "
                       if interest == "needs pricing info" else "")
                    + ("Let them know we'll schedule a demo and someone will email them shortly. "
                       if interest == "wants a demo" else "")
                    + "Thank them warmly for their time."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    f"Thank {self.contact_name} sincerely for their honest feedback. "
                    "Let them know we appreciate them sharing their thoughts and that the "
                    "feedback will be passed to the product team. "
                    + (f"If they mentioned something specific we could improve ('{missing}'), "
                       "acknowledge it genuinely. " if missing else "")
                    + "Wish them well."
                )
            )

    def recipient_unavailable(self):
        logging.info("Unable to reach %s for re-engagement call.", self.contact_name)
        try:
            tag_contact(self.contact_id, "reengagement-called")
            tag_contact(self.contact_id, "voicemail-left")
        except Exception as e:
            logging.error("Failed to tag contact %s: %s", self.contact_id, e)

        self.hangup(
            final_instructions=(
                f"Leave a brief, warm voicemail for {self.contact_name} from Stackline. "
                "Let them know you're calling to check in and that you'd love to reconnect. "
                "Keep it light — no pressure. Ask them to call back or reply to any recent emails."
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Outbound re-engagement call for an inactive Intercom contact."
    )
    parser.add_argument("phone", help="Contact's phone number (E.164, e.g. +15551234567)")
    parser.add_argument("--contact-id", required=True, help="Intercom contact ID")
    parser.add_argument("--name", required=True, help="Full name of the contact to reach")
    args = parser.parse_args()

    logging.info("Initiating re-engagement call to %s (%s)", args.name, args.phone)

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=OutboundReengagementController(
            contact_id=args.contact_id,
            contact_name=args.name,
        ),
    )

import guava
import os
import logging
from guava import logging_utils
import argparse
import requests
from datetime import datetime, timezone


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


agent = guava.Agent(
    name="Casey",
    organization="Stackline",
    purpose=(
        "to re-engage lapsed Stackline customers, understand why they stopped using "
        "the product, and explore whether there's a path to bringing them back"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    contact_id = call.get_variable("contact_id")
    contact_name = call.get_variable("contact_name")

    contact_email = ""
    last_seen = ""
    try:
        contact = get_contact(contact_id)
        if contact:
            contact_email = contact.get("email") or ""
            last_ts = contact.get("last_seen_at")
            if last_ts:
                last_seen = datetime.fromtimestamp(last_ts, tz=timezone.utc).strftime("%B %Y")
    except Exception as e:
        logging.error("Failed to fetch contact %s pre-call: %s", contact_id, e)

    call.set_variable("last_seen", last_seen)

    call.reach_person(contact_full_name=contact_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    contact_name = call.get_variable("contact_name")
    contact_id = call.get_variable("contact_id")

    if outcome == "unavailable":
        logging.info("Unable to reach %s for re-engagement call.", contact_name)
        try:
            tag_contact(contact_id, "reengagement-called")
            tag_contact(contact_id, "voicemail-left")
        except Exception as e:
            logging.error("Failed to tag contact %s: %s", contact_id, e)

        call.hangup(
            final_instructions=(
                f"Leave a brief, warm voicemail for {contact_name} from Stackline. "
                "Let them know you're calling to check in and that you'd love to reconnect. "
                "Keep it light — no pressure. Ask them to call back or reply to any recent emails."
            )
        )
    elif outcome == "available":
        last_seen = call.get_variable("last_seen") or ""
        last_seen_note = f" We noticed you haven't been active since {last_seen}." if last_seen else ""

        call.set_task(
            "record_outcome",
            objective=(
                f"Re-engage {contact_name} who has been inactive on Stackline. "
                "Understand their experience, whether they moved to a competitor, and whether "
                "there's any opportunity to bring them back."
            ),
            checklist=[
                guava.Say(
                    f"Hi {contact_name}, this is Casey from Stackline.{last_seen_note} "
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
        )


@agent.on_task_complete("record_outcome")
def on_done(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    contact_id = call.get_variable("contact_id")

    still_using = call.get_field("still_using") or "haven't used it in a while"
    reason = call.get_field("reason_for_lapse") or ""
    interest = call.get_field("reengagement_interest") or "not interested"
    missing = call.get_field("missing_feature") or ""

    tag = OUTCOME_TAGS.get(interest, "contacted")

    logging.info(
        "Re-engagement call complete for %s — interest: %s", contact_name, interest,
    )

    try:
        tag_contact(contact_id, tag)
        tag_contact(contact_id, "reengagement-called")
        logging.info("Tags applied to contact %s.", contact_id)
    except Exception as e:
        logging.error("Failed to tag contact %s: %s", contact_id, e)

    custom_attrs = {
        "reengagement_outcome": interest,
        "reengagement_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }
    try:
        update_contact(contact_id, {"custom_attributes": custom_attrs})
        logging.info("Contact %s updated with reengagement outcome.", contact_id)
    except Exception as e:
        logging.error("Failed to update contact %s: %s", contact_id, e)

    if interest in ("interested in returning", "needs pricing info", "wants a demo"):
        call.hangup(
            final_instructions=(
                f"Express genuine excitement about reconnecting with {contact_name}. "
                + ("Let them know the sales team will reach out with updated pricing within one business day. "
                   if interest == "needs pricing info" else "")
                + ("Let them know we'll schedule a demo and someone will email them shortly. "
                   if interest == "wants a demo" else "")
                + "Thank them warmly for their time."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {contact_name} sincerely for their honest feedback. "
                "Let them know we appreciate them sharing their thoughts and that the "
                "feedback will be passed to the product team. "
                + (f"If they mentioned something specific we could improve ('{missing}'), "
                   "acknowledge it genuinely. " if missing else "")
                + "Wish them well."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound re-engagement call for an inactive Intercom contact."
    )
    parser.add_argument("phone", help="Contact's phone number (E.164, e.g. +15551234567)")
    parser.add_argument("--contact-id", required=True, help="Intercom contact ID")
    parser.add_argument("--name", required=True, help="Full name of the contact to reach")
    args = parser.parse_args()

    logging.info("Initiating re-engagement call to %s (%s)", args.name, args.phone)

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "contact_id": args.contact_id,
            "contact_name": args.name,
        },
    )

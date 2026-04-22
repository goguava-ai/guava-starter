import guava
import os
import logging
from guava import logging_utils
import argparse
import requests
from datetime import datetime, timezone


HUBSPOT_ACCESS_TOKEN = os.environ["HUBSPOT_ACCESS_TOKEN"]
HEADERS = {
    "Authorization": f"Bearer {HUBSPOT_ACCESS_TOKEN}",
    "Content-Type": "application/json",
}
BASE_URL = "https://api.hubapi.com"


def get_deal(deal_id: str) -> dict | None:
    resp = requests.get(
        f"{BASE_URL}/crm/objects/2026-03/deals/{deal_id}",
        headers=HEADERS,
        params={"properties": "dealname,amount,closedate,dealstage"},
        timeout=10,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def update_deal_stage(deal_id: str, stage: str) -> None:
    resp = requests.patch(
        f"{BASE_URL}/crm/objects/2026-03/deals/{deal_id}",
        headers=HEADERS,
        json={"properties": {"dealstage": stage}},
        timeout=10,
    )
    resp.raise_for_status()


def log_note_on_deal(deal_id: str, note_body: str) -> None:
    """Creates a note and associates it with the given deal."""
    payload = {
        "properties": {
            "hs_note_body": note_body,
            "hs_timestamp": datetime.now(timezone.utc).isoformat(),
        },
        "associations": [
            {
                "to": {"id": deal_id},
                "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 214}],
            }
        ],
    }
    resp = requests.post(
        f"{BASE_URL}/crm/objects/2026-03/notes",
        headers=HEADERS,
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()


class RenewalOutreachController(guava.CallController):
    def __init__(self, deal_id: str, customer_name: str):
        super().__init__()
        self.deal_id = deal_id
        self.customer_name = customer_name
        self.deal_name = "your current plan"
        self.deal_amount = ""
        self.close_date = ""

        try:
            deal = get_deal(deal_id)
            if deal:
                props = deal.get("properties", {})
                if props.get("dealname"):
                    self.deal_name = props["dealname"]
                if props.get("amount"):
                    self.deal_amount = f"${float(props['amount']):,.0f}"
                if props.get("closedate"):
                    dt = datetime.strptime(props["closedate"][:10], "%Y-%m-%d")
                    self.close_date = dt.strftime("%B %d, %Y")
        except Exception as e:
            logging.error("Failed to fetch deal %s pre-call: %s", deal_id, e)

        self.set_persona(
            organization_name="Apex Solutions",
            agent_name="Morgan",
            agent_purpose=(
                "to reach out to customers ahead of their contract renewal and understand "
                "their intent to continue with Apex Solutions"
            ),
        )

        self.reach_person(
            contact_full_name=self.customer_name,
            on_success=self.begin_renewal_conversation,
            on_failure=self.recipient_unavailable,
        )

    def begin_renewal_conversation(self):
        amount_note = f" valued at {self.deal_amount}" if self.deal_amount else ""
        date_note = f" on {self.close_date}" if self.close_date else " coming up soon"

        self.set_task(
            objective=(
                f"Speak with {self.customer_name} about renewing '{self.deal_name}'"
                f"{amount_note}, with their renewal date{date_note}. "
                "Understand their renewal intent and capture any concerns."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.customer_name}, this is Morgan calling from Apex Solutions. "
                    f"I'm reaching out because your contract is coming up for renewal{date_note} "
                    "and I wanted to connect personally to make sure everything is going well "
                    "and talk through next steps."
                ),
                guava.Field(
                    key="satisfaction",
                    field_type="multiple_choice",
                    description=(
                        "Ask how satisfied they've been overall. "
                        "'How has your experience with Apex Solutions been?'"
                    ),
                    choices=["very satisfied", "satisfied", "neutral", "dissatisfied"],
                    required=True,
                ),
                guava.Field(
                    key="renewal_intent",
                    field_type="multiple_choice",
                    description=(
                        "Ask about their renewal plans. "
                        "'Are you planning to continue with us at renewal?'"
                    ),
                    choices=[
                        "yes/renew as-is",
                        "yes/would like to upgrade",
                        "undecided",
                        "planning to cancel",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="concerns",
                    field_type="text",
                    description=(
                        "If they are undecided or planning to cancel, ask what concerns or "
                        "hesitations they have. Skip if they intend to renew."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="preferred_followup",
                    field_type="multiple_choice",
                    description="Ask how they'd prefer we follow up with renewal paperwork.",
                    choices=["email", "phone call", "both"],
                    required=True,
                ),
            ],
            on_complete=self.record_outcome,
        )

    def record_outcome(self):
        satisfaction = self.get_field("satisfaction") or "unknown"
        intent = self.get_field("renewal_intent") or "unknown"
        concerns = self.get_field("concerns") or ""
        followup = self.get_field("preferred_followup") or "email"

        logging.info(
            "Renewal outcome for deal %s — intent: %s, satisfaction: %s",
            self.deal_id, intent, satisfaction,
        )

        stage_map = {
            "yes/renew as-is": "contractsent",
            "yes/would like to upgrade": "decisionmakerboughtin",
            "undecided": "presentationscheduled",
            "planning to cancel": "closedlost",
        }

        note_lines = [
            f"Renewal outreach call — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
            f"Customer: {self.customer_name}",
            f"Satisfaction: {satisfaction}",
            f"Renewal intent: {intent}",
            f"Preferred follow-up: {followup}",
        ]
        if concerns:
            note_lines.append(f"Concerns: {concerns}")

        try:
            new_stage = stage_map.get(intent)
            if new_stage:
                update_deal_stage(self.deal_id, new_stage)
                logging.info("Updated deal %s to stage %s", self.deal_id, new_stage)
            log_note_on_deal(self.deal_id, "\n".join(note_lines))
        except Exception as e:
            logging.error("Failed to update HubSpot for deal %s: %s", self.deal_id, e)

        if intent == "planning to cancel":
            self.hangup(
                final_instructions=(
                    f"Express genuine concern and empathy to {self.customer_name}. "
                    "Let them know their feedback has been noted and a customer success manager "
                    "will reach out personally to understand their concerns and see what we can do. "
                    "Thank them sincerely for being a customer."
                )
            )
        elif intent in ("yes/renew as-is", "yes/would like to upgrade"):
            email_note = "We'll send renewal paperwork via email shortly. " if followup in ("email", "both") else ""
            call_note = "Someone will call to walk through the paperwork. " if followup in ("phone call", "both") else ""
            self.hangup(
                final_instructions=(
                    f"Thank {self.customer_name} enthusiastically for their continued loyalty. "
                    + email_note
                    + call_note
                    + "Wish them a great day."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    f"Thank {self.customer_name} for their honesty. "
                    "Let them know a customer success manager will be in touch to answer questions "
                    "and explore the best path forward. Assure them there's no pressure. "
                    "Wish them a great day."
                )
            )

    def recipient_unavailable(self):
        logging.info(
            "Unable to reach %s for renewal outreach on deal %s",
            self.customer_name, self.deal_id,
        )
        try:
            log_note_on_deal(
                self.deal_id,
                f"Renewal outreach attempted — {self.customer_name} unavailable, voicemail left.",
            )
        except Exception as e:
            logging.error("Failed to log note for deal %s: %s", self.deal_id, e)

        self.hangup(
            final_instructions=(
                f"Leave a friendly voicemail for {self.customer_name} on behalf of Apex Solutions. "
                f"Let them know you're calling about their upcoming renewal for {self.deal_name} "
                "and ask them to call back or look out for an email from our team with next steps. "
                "Keep it brief and warm."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound renewal outreach call for a HubSpot deal."
    )
    parser.add_argument("phone", help="Customer phone number (E.164, e.g. +15551234567)")
    parser.add_argument("--deal-id", required=True, help="HubSpot deal ID")
    parser.add_argument("--name", required=True, help="Customer's full name")
    args = parser.parse_args()

    logging.info(
        "Initiating renewal outreach to %s (%s) for deal %s",
        args.name, args.phone, args.deal_id,
    )

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=RenewalOutreachController(
            deal_id=args.deal_id,
            customer_name=args.name,
        ),
    )

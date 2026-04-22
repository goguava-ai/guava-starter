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
        params={"properties": "dealname,amount"},
        timeout=10,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def log_survey_note(deal_id: str, contact_id: str, note_body: str) -> None:
    """Creates a note associated with both the deal and the contact."""
    payload = {
        "properties": {
            "hs_note_body": note_body,
            "hs_timestamp": datetime.now(timezone.utc).isoformat(),
        },
        "associations": [
            {
                "to": {"id": deal_id},
                "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 214}],
            },
            {
                "to": {"id": contact_id},
                "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 202}],
            },
        ],
    }
    resp = requests.post(
        f"{BASE_URL}/crm/objects/2026-03/notes",
        headers=HEADERS,
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()


class WinLossSurveyController(guava.CallController):
    def __init__(self, deal_id: str, contact_id: str, customer_name: str, outcome: str):
        super().__init__()
        self.deal_id = deal_id
        self.contact_id = contact_id
        self.customer_name = customer_name
        self.outcome = outcome  # "won" or "lost"
        self.deal_name = "our recent proposal"

        try:
            deal = get_deal(deal_id)
            if deal and deal.get("properties", {}).get("dealname"):
                self.deal_name = deal["properties"]["dealname"]
        except Exception as e:
            logging.error("Failed to fetch deal %s pre-call: %s", deal_id, e)

        self.set_persona(
            organization_name="Apex Solutions",
            agent_name="Casey",
            agent_purpose=(
                "to conduct a brief win/loss interview with prospects and customers "
                "to help Apex Solutions learn and improve"
            ),
        )

        self.reach_person(
            contact_full_name=self.customer_name,
            on_success=self.begin_survey,
            on_failure=self.recipient_unavailable,
        )

    def begin_survey(self):
        if self.outcome == "won":
            opener = (
                f"Hi {self.customer_name}, this is Casey from Apex Solutions. "
                "I'm reaching out to personally thank you for choosing us and ask a couple of "
                "quick questions about your decision — your feedback helps us keep doing our best work. "
                "Do you have just two or three minutes?"
            )
            objective = (
                f"Conduct a brief win interview with {self.customer_name} "
                f"about '{self.deal_name}'. Understand why they chose Apex Solutions."
            )
            checklist = [
                guava.Say(opener),
                guava.Field(
                    key="primary_reason",
                    field_type="text",
                    description="Ask: 'What was the main reason you chose Apex Solutions?'",
                    required=True,
                ),
                guava.Field(
                    key="standout_factor",
                    field_type="multiple_choice",
                    description="Ask what stood out most during their evaluation.",
                    choices=[
                        "product features",
                        "pricing",
                        "support/service",
                        "brand reputation",
                        "ease of use",
                        "other",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="improvement_suggestion",
                    field_type="text",
                    description="Ask: 'Is there anything we could do even better?'",
                    required=False,
                ),
            ]
        else:
            opener = (
                f"Hi {self.customer_name}, this is Casey from Apex Solutions. "
                "I know you went in a different direction recently, and that's completely understandable. "
                "I'm calling simply to learn from your experience — your feedback genuinely helps us improve. "
                "Would you be open to sharing a few thoughts? It'll only take two or three minutes."
            )
            objective = (
                f"Conduct a brief loss interview with {self.customer_name} "
                f"about '{self.deal_name}'. Understand why they chose a competitor."
            )
            checklist = [
                guava.Say(opener),
                guava.Field(
                    key="primary_reason",
                    field_type="text",
                    description="Ask: 'What was the main reason you went with a different provider?'",
                    required=True,
                ),
                guava.Field(
                    key="competitor_chosen",
                    field_type="text",
                    description=(
                        "Ask if they're comfortable sharing who they chose instead. "
                        "Do not press if they'd rather not say."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="improvement_suggestion",
                    field_type="text",
                    description="Ask: 'What could we have done differently to win your business?'",
                    required=True,
                ),
                guava.Field(
                    key="likely_to_return",
                    field_type="multiple_choice",
                    description="Ask: 'Is Apex Solutions something you might consider again in the future?'",
                    choices=["yes", "maybe", "unlikely"],
                    required=True,
                ),
            ]

        self.set_task(
            objective=objective,
            checklist=checklist,
            on_complete=self.save_survey,
        )

    def save_survey(self):
        primary_reason = self.get_field("primary_reason") or ""
        improvement = self.get_field("improvement_suggestion") or ""
        standout = self.get_field("standout_factor") or ""
        competitor = self.get_field("competitor_chosen") or ""
        likely_to_return = self.get_field("likely_to_return") or ""

        note_lines = [
            f"Win/Loss Survey — {self.outcome.upper()} — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
            f"Contact: {self.customer_name}",
            f"Deal: {self.deal_name}",
            f"Primary reason: {primary_reason}",
        ]
        if standout:
            note_lines.append(f"Standout factor: {standout}")
        if competitor:
            note_lines.append(f"Competitor chosen: {competitor}")
        if improvement:
            note_lines.append(f"Suggestions for improvement: {improvement}")
        if likely_to_return:
            note_lines.append(f"Likely to return: {likely_to_return}")

        logging.info("Win/loss survey complete for deal %s (%s)", self.deal_id, self.outcome)

        try:
            log_survey_note(self.deal_id, self.contact_id, "\n".join(note_lines))
            logging.info(
                "Survey note saved to deal %s and contact %s", self.deal_id, self.contact_id
            )
        except Exception as e:
            logging.error("Failed to save survey note: %s", e)

        if self.outcome == "won":
            self.hangup(
                final_instructions=(
                    f"Thank {self.customer_name} sincerely for their time and for choosing "
                    "Apex Solutions. Let them know their feedback is valuable. "
                    "Express genuine excitement about working together and wish them a great day."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    f"Thank {self.customer_name} genuinely for their candid feedback. "
                    "Let them know their insights will directly help the team improve. "
                    "Wish them success with their new provider and let them know the door "
                    "is always open if they'd like to revisit Apex Solutions in the future."
                )
            )

    def recipient_unavailable(self):
        logging.info(
            "Unable to reach %s for win/loss survey on deal %s",
            self.customer_name, self.deal_id,
        )
        self.hangup(
            final_instructions=(
                f"Leave a brief, warm voicemail for {self.customer_name} on behalf of Apex Solutions. "
                "Let them know you were hoping to gather a couple minutes of feedback on their "
                "recent decision and that no action is required — you'll follow up by email. "
                "Thank them for their time."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound win/loss survey call for a closed HubSpot deal."
    )
    parser.add_argument("phone", help="Contact's phone number (E.164, e.g. +15551234567)")
    parser.add_argument("--deal-id", required=True, help="HubSpot deal ID")
    parser.add_argument("--contact-id", required=True, help="HubSpot contact ID")
    parser.add_argument("--name", required=True, help="Contact's full name")
    parser.add_argument(
        "--outcome", required=True, choices=["won", "lost"], help="Deal outcome"
    )
    args = parser.parse_args()

    logging.info(
        "Initiating win/loss survey to %s (%s) — deal %s, outcome: %s",
        args.name, args.phone, args.deal_id, args.outcome,
    )

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=WinLossSurveyController(
            deal_id=args.deal_id,
            contact_id=args.contact_id,
            customer_name=args.name,
            outcome=args.outcome,
        ),
    )

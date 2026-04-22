import guava
import os
import logging
from guava import logging_utils
import base64
import argparse
import requests
from datetime import datetime, timezone


ZENDESK_SUBDOMAIN = os.environ["ZENDESK_SUBDOMAIN"]
ZENDESK_EMAIL = os.environ["ZENDESK_EMAIL"]
ZENDESK_API_TOKEN = os.environ["ZENDESK_API_TOKEN"]

_encoded = base64.b64encode(f"{ZENDESK_EMAIL}/token:{ZENDESK_API_TOKEN}".encode()).decode()
HEADERS = {
    "Authorization": f"Basic {_encoded}",
    "Content-Type": "application/json",
}
BASE_URL = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com/api/v2"


def get_ticket(ticket_id: str) -> dict | None:
    """Fetches a single Zendesk ticket by ID."""
    resp = requests.get(f"{BASE_URL}/tickets/{ticket_id}", headers=HEADERS, timeout=10)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()["ticket"]


def add_internal_note(ticket_id: str, body: str) -> None:
    """Posts a private internal note to the ticket with the survey results."""
    payload = {
        "ticket": {
            "comment": {
                "body": body,
                "public": False,
            }
        }
    }
    resp = requests.put(
        f"{BASE_URL}/tickets/{ticket_id}",
        headers=HEADERS,
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()


class CsatSurveyController(guava.CallController):
    def __init__(self, ticket_id: str, customer_name: str):
        super().__init__()
        self.ticket_id = ticket_id
        self.customer_name = customer_name
        self.ticket_subject = "your recent support request"

        # Pre-call: fetch the ticket to personalize the survey with the issue subject.
        try:
            ticket = get_ticket(ticket_id)
            if ticket and ticket.get("subject"):
                self.ticket_subject = f"'{ticket['subject']}'"
        except Exception as e:
            logging.error("Failed to fetch ticket #%s pre-call: %s", ticket_id, e)

        self.set_persona(
            organization_name="Horizon Software",
            agent_name="Morgan",
            agent_purpose=(
                "to collect customer satisfaction feedback on behalf of Horizon Software "
                "after a support ticket has been resolved"
            ),
        )

        self.reach_person(
            contact_full_name=self.customer_name,
            on_success=self.begin_survey,
            on_failure=self.recipient_unavailable,
        )

    def begin_survey(self):
        self.set_task(
            objective=(
                f"Collect CSAT feedback from {self.customer_name} regarding their recently "
                f"resolved ticket {self.ticket_subject}."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.customer_name}, this is Morgan calling from Horizon Software. "
                    f"I'm following up on your recently resolved support ticket regarding "
                    f"{self.ticket_subject}. I have just a couple of quick questions — "
                    "this will only take about a minute."
                ),
                guava.Field(
                    key="satisfaction_rating",
                    field_type="multiple_choice",
                    description=(
                        "Ask: 'On a scale of 1 to 5 — where 1 is very dissatisfied and 5 is very "
                        "satisfied — how would you rate the support you received?' "
                        "Capture their numeric rating."
                    ),
                    choices=["1", "2", "3", "4", "5"],
                    required=True,
                ),
                guava.Field(
                    key="resolution_quality",
                    field_type="multiple_choice",
                    description=(
                        "Ask: 'Was your issue fully resolved to your satisfaction?' "
                        "Capture their answer."
                    ),
                    choices=["yes", "partially", "no"],
                    required=True,
                ),
                guava.Field(
                    key="open_feedback",
                    field_type="text",
                    description=(
                        "Ask: 'Is there anything we could have done better, or any other "
                        "feedback you'd like to share?' Capture their response, or 'none' "
                        "if they have nothing to add."
                    ),
                    required=False,
                ),
            ],
            on_complete=self.save_results,
        )

    def save_results(self):
        rating = self.get_field("satisfaction_rating") or "not provided"
        resolution = self.get_field("resolution_quality") or "not provided"
        feedback = self.get_field("open_feedback") or ""

        logging.info(
            "CSAT results for ticket #%s — rating: %s, resolved: %s",
            self.ticket_id, rating, resolution,
        )

        # Post an internal note to the ticket so the CSAT data lives alongside the case.
        note_lines = [
            f"CSAT survey completed — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            f"Customer: {self.customer_name}",
            f"Satisfaction rating: {rating}/5",
            f"Issue fully resolved: {resolution}",
        ]
        if feedback and feedback.strip().lower() not in ("none", "n/a", ""):
            note_lines.append(f"Open feedback: {feedback}")

        try:
            add_internal_note(self.ticket_id, "\n".join(note_lines))
            logging.info("CSAT note added to ticket #%s", self.ticket_id)
        except Exception as e:
            logging.error("Failed to save CSAT note to ticket #%s: %s", self.ticket_id, e)

        rating_int = int(rating) if rating.isdigit() else 0
        if rating_int <= 2:
            self.hangup(
                final_instructions=(
                    f"Sincerely thank {self.customer_name} for their candid feedback. "
                    "Acknowledge that we fell short of their expectations and let them know "
                    "a member of our team will personally follow up to make things right. "
                    "Apologize again and wish them a good day."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    f"Thank {self.customer_name} warmly for taking the time to share their feedback. "
                    "Let them know their input helps us improve our support team. "
                    "Wish them a great day and let them know we're here if they need anything else."
                )
            )

    def recipient_unavailable(self):
        logging.info(
            "Unable to reach %s for ticket #%s CSAT survey", self.customer_name, self.ticket_id
        )
        self.hangup(
            final_instructions=(
                "Leave a brief, friendly voicemail on behalf of Horizon Software letting the "
                "customer know we were calling to follow up on their recently resolved support "
                "ticket. Let them know no action is needed and we hope everything is working well."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound CSAT survey call for a resolved Zendesk ticket."
    )
    parser.add_argument("phone", help="Customer phone number to call (E.164 format, e.g. +15551234567)")
    parser.add_argument("--ticket-id", required=True, help="Zendesk ticket ID")
    parser.add_argument("--name", required=True, help="Customer's full name")
    args = parser.parse_args()

    logging.info(
        "Initiating CSAT survey call to %s (%s) for ticket #%s",
        args.name, args.phone, args.ticket_id,
    )

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=CsatSurveyController(
            ticket_id=args.ticket_id,
            customer_name=args.name,
        ),
    )

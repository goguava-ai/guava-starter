import guava
import os
import logging
import argparse
import requests
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)

TOKEN = os.environ["KUSTOMER_API_TOKEN"]
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
BASE_URL = "https://api.kustomerapp.com/v1"


def get_conversation(conversation_id: str) -> dict | None:
    """Fetches a single conversation by ID. Returns the conversation object or None."""
    resp = requests.get(
        f"{BASE_URL}/conversations/{conversation_id}",
        headers=HEADERS,
        timeout=10,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    data = resp.json().get("data")
    return data if data else None


def add_note(conversation_id: str, body: str) -> dict:
    """Posts an internal note to a conversation. Returns the note object."""
    payload = {"body": body}
    resp = requests.post(
        f"{BASE_URL}/conversations/{conversation_id}/notes",
        headers=HEADERS,
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["data"]


def update_conversation(conversation_id: str, tags: list[str]) -> dict:
    """Patches a conversation to add tags. Returns the updated conversation object."""
    payload = {"tags": tags}
    resp = requests.patch(
        f"{BASE_URL}/conversations/{conversation_id}",
        headers=HEADERS,
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["data"]


class CsatSurveyController(guava.CallController):
    def __init__(self, conv_id: str, customer_name: str):
        super().__init__()
        self.conv_id = conv_id
        self.customer_name = customer_name
        self.issue_summary = "your recent support case"

        # Pre-call: fetch the conversation to personalize the survey.
        try:
            conversation = get_conversation(conv_id)
            if conversation:
                attrs = conversation.get("attributes", {})
                preview = attrs.get("preview") or attrs.get("subject") or ""
                if preview:
                    self.issue_summary = f"'{preview}'"
        except Exception as e:
            logging.error("Failed to fetch conversation %s pre-call: %s", conv_id, e)

        self.set_persona(
            organization_name="Brightpath Support",
            agent_name="Morgan",
            agent_purpose=(
                "to collect customer satisfaction feedback on behalf of Brightpath Support "
                "after a support case has been resolved"
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
                f"resolved support case {self.issue_summary}."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.customer_name}, this is Morgan calling from Brightpath Support. "
                    f"I'm following up on your recently resolved support case regarding "
                    f"{self.issue_summary}. I have just a couple of quick questions — "
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
                        "Ask: 'Was your issue fully resolved, partially resolved, or not resolved?' "
                        "Capture their answer."
                    ),
                    choices=["fully-resolved", "partially-resolved", "not-resolved"],
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
            "CSAT results for conversation %s — rating: %s, resolved: %s",
            self.conv_id, rating, resolution,
        )

        # Build the internal note body
        note_lines = [
            f"CSAT survey completed — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            f"Customer: {self.customer_name}",
            f"Satisfaction rating: {rating}/5",
            f"Resolution quality: {resolution}",
        ]
        if feedback and feedback.strip().lower() not in ("none", "n/a", ""):
            note_lines.append(f"Open feedback: {feedback}")

        try:
            add_note(self.conv_id, "\n".join(note_lines))
            logging.info("CSAT note added to conversation %s", self.conv_id)
        except Exception as e:
            logging.error("Failed to add CSAT note to conversation %s: %s", self.conv_id, e)

        # Tag the conversation to record that CSAT was collected
        try:
            update_conversation(self.conv_id, tags=["guava", "voice", "csat-collected"])
            logging.info("Tagged conversation %s with csat-collected", self.conv_id)
        except Exception as e:
            logging.error("Failed to tag conversation %s: %s", self.conv_id, e)

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
                    "Wish them a great day and let them know we're here if they ever need anything."
                )
            )

    def recipient_unavailable(self):
        logging.info(
            "Unable to reach %s for conversation %s CSAT survey",
            self.customer_name, self.conv_id,
        )
        self.hangup(
            final_instructions=(
                "Leave a brief, friendly voicemail on behalf of Brightpath Support letting the "
                "customer know we were calling to follow up on their recently resolved support "
                "case. Let them know no action is needed and we hope everything is working well."
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Outbound CSAT survey call for a resolved Kustomer conversation."
    )
    parser.add_argument("phone", help="Customer phone number to call (E.164 format, e.g. +15551234567)")
    parser.add_argument("--conv-id", required=True, help="Kustomer conversation ID")
    parser.add_argument("--name", required=True, help="Customer's full name")
    args = parser.parse_args()

    logging.info(
        "Initiating CSAT survey call to %s (%s) for conversation %s",
        args.name, args.phone, args.conv_id,
    )

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=CsatSurveyController(
            conv_id=args.conv_id,
            customer_name=args.name,
        ),
    )

import guava
import os
import logging
import argparse
import requests
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)

HUBSPOT_ACCESS_TOKEN = os.environ["HUBSPOT_ACCESS_TOKEN"]
HEADERS = {
    "Authorization": f"Bearer {HUBSPOT_ACCESS_TOKEN}",
    "Content-Type": "application/json",
}
BASE_URL = "https://api.hubapi.com"


def get_contact(contact_id: str) -> dict | None:
    resp = requests.get(
        f"{BASE_URL}/crm/objects/2026-03/contacts/{contact_id}",
        headers=HEADERS,
        params={"properties": "firstname,lastname,email,company,jobtitle"},
        timeout=10,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def log_followup_note(contact_id: str, note_body: str) -> None:
    """Creates a follow-up note associated with the contact."""
    payload = {
        "properties": {
            "hs_note_body": note_body,
            "hs_timestamp": datetime.now(timezone.utc).isoformat(),
        },
        "associations": [
            {
                "to": {"id": contact_id},
                "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 202}],
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


def update_contact_lifecycle(contact_id: str, stage: str) -> None:
    resp = requests.patch(
        f"{BASE_URL}/crm/objects/2026-03/contacts/{contact_id}",
        headers=HEADERS,
        json={"properties": {"lifecyclestage": stage}},
        timeout=10,
    )
    resp.raise_for_status()


class MeetingFollowupController(guava.CallController):
    def __init__(self, contact_id: str, customer_name: str, meeting_topic: str):
        super().__init__()
        self.contact_id = contact_id
        self.customer_name = customer_name
        self.meeting_topic = meeting_topic
        self.company = ""

        try:
            contact = get_contact(contact_id)
            if contact:
                self.company = contact.get("properties", {}).get("company") or ""
        except Exception as e:
            logging.error("Failed to fetch contact %s pre-call: %s", contact_id, e)

        self.set_persona(
            organization_name="Apex Solutions",
            agent_name="Alex",
            agent_purpose=(
                "to follow up with prospects after a meeting or demo and understand "
                "their reaction and next steps"
            ),
        )

        self.reach_person(
            contact_full_name=self.customer_name,
            on_success=self.begin_followup,
            on_failure=self.recipient_unavailable,
        )

    def begin_followup(self):
        company_note = f" at {self.company}" if self.company else ""

        self.set_task(
            objective=(
                f"Follow up with {self.customer_name}{company_note} after their recent meeting "
                f"about '{self.meeting_topic}'. Gauge their reaction, address any questions, "
                "and agree on a clear next step."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.customer_name}, this is Alex from Apex Solutions. "
                    f"I'm following up on our recent meeting about {self.meeting_topic}. "
                    "I just wanted to check in and see how you're feeling about everything we discussed."
                ),
                guava.Field(
                    key="overall_impression",
                    field_type="multiple_choice",
                    description="Ask how they felt about the meeting overall.",
                    choices=["very positive", "positive", "neutral", "had some concerns"],
                    required=True,
                ),
                guava.Field(
                    key="questions_or_concerns",
                    field_type="text",
                    description=(
                        "Ask if they have any questions or concerns from what was covered. "
                        "Capture the full question or concern if they have one."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="internal_alignment",
                    field_type="multiple_choice",
                    description=(
                        "Ask if they've had a chance to share what they learned with other "
                        "stakeholders internally."
                    ),
                    choices=[
                        "yes/positive reception",
                        "yes/more questions",
                        "not yet",
                        "not needed",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="next_step",
                    field_type="multiple_choice",
                    description="Ask what they see as a good next step.",
                    choices=[
                        "schedule another call",
                        "send a proposal",
                        "start a trial",
                        "need more time to evaluate",
                        "not moving forward",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="next_step_timing",
                    field_type="multiple_choice",
                    description="If a next step was agreed, ask when works best.",
                    choices=["this week", "next week", "within the month", "no rush"],
                    required=False,
                ),
            ],
            on_complete=self.record_followup,
        )

    def record_followup(self):
        impression = self.get_field("overall_impression") or "unknown"
        questions = self.get_field("questions_or_concerns") or ""
        alignment = self.get_field("internal_alignment") or "unknown"
        next_step = self.get_field("next_step") or "unknown"
        timing = self.get_field("next_step_timing") or ""

        note_lines = [
            f"Post-meeting follow-up — {datetime.utcnow().strftime('%Y-%m-%d')}",
            f"Meeting topic: {self.meeting_topic}",
            f"Overall impression: {impression}",
            f"Internal alignment: {alignment}",
            f"Agreed next step: {next_step}",
        ]
        if timing:
            note_lines.append(f"Next step timing: {timing}")
        if questions:
            note_lines.append(f"Questions/concerns: {questions}")

        logging.info(
            "Meeting follow-up complete for contact %s — next step: %s",
            self.contact_id, next_step,
        )

        try:
            log_followup_note(self.contact_id, "\n".join(note_lines))
            if next_step in ("send a proposal", "start a trial", "schedule another call"):
                update_contact_lifecycle(self.contact_id, "opportunity")
            logging.info("Follow-up note saved for contact %s", self.contact_id)
        except Exception as e:
            logging.error("Failed to save follow-up note for contact %s: %s", self.contact_id, e)

        if next_step == "not moving forward":
            self.hangup(
                final_instructions=(
                    f"Thank {self.customer_name} warmly for their time and for meeting with us. "
                    "Respect their decision and let them know the door is always open if anything changes. "
                    "Wish them all the best."
                )
            )
        else:
            timing_phrase = f" — ideally {timing}" if timing else ""
            self.hangup(
                final_instructions=(
                    f"Confirm the agreed next step with {self.customer_name}: {next_step}{timing_phrase}. "
                    "Let them know you'll send a follow-up email summarizing what was discussed. "
                    "Thank them for their time and express genuine excitement. Wish them a great day."
                )
            )

    def recipient_unavailable(self):
        logging.info("Unable to reach %s for meeting follow-up", self.customer_name)
        try:
            log_followup_note(
                self.contact_id,
                f"Post-meeting follow-up call attempted — {self.customer_name} not available, voicemail left. "
                f"Meeting topic: {self.meeting_topic}.",
            )
        except Exception as e:
            logging.error("Failed to log note for contact %s: %s", self.contact_id, e)

        self.hangup(
            final_instructions=(
                f"Leave a brief, warm voicemail for {self.customer_name} on behalf of Apex Solutions. "
                f"Let them know you're following up on your recent meeting about {self.meeting_topic} "
                "and that you'll send a quick email as well. "
                "Let them know they can reach you at the number you're calling from. "
                "Keep it friendly and brief."
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Outbound post-meeting follow-up call.")
    parser.add_argument("phone", help="Contact's phone number (E.164, e.g. +15551234567)")
    parser.add_argument("--contact-id", required=True, help="HubSpot contact ID")
    parser.add_argument("--name", required=True, help="Contact's full name")
    parser.add_argument(
        "--meeting-topic",
        required=True,
        help="Topic or title of the meeting (e.g. 'your product demo')",
    )
    args = parser.parse_args()

    logging.info("Initiating meeting follow-up call to %s (%s)", args.name, args.phone)

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=MeetingFollowupController(
            contact_id=args.contact_id,
            customer_name=args.name,
            meeting_topic=args.meeting_topic,
        ),
    )

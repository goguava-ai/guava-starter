import guava
import os
import logging
import argparse
import requests
from datetime import datetime

logging.basicConfig(level=logging.INFO)

GRAPH_ACCESS_TOKEN = os.environ["GRAPH_ACCESS_TOKEN"]
BASE_URL = "https://graph.microsoft.com/v1.0"
HEADERS = {
    "Authorization": f"Bearer {GRAPH_ACCESS_TOKEN}",
    "Content-Type": "application/json",
}


def get_message(user_id: str, message_id: str) -> dict:
    """Fetches a specific message from the user's mailbox."""
    resp = requests.get(
        f"{BASE_URL}/users/{user_id}/messages/{message_id}",
        headers=HEADERS,
        params={"$select": "subject,from,body,receivedDateTime,importance,bodyPreview"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def flag_message(user_id: str, message_id: str) -> None:
    """Marks a message as flagged for follow-up."""
    requests.patch(
        f"{BASE_URL}/users/{user_id}/messages/{message_id}",
        headers=HEADERS,
        json={"flag": {"flagStatus": "flagged"}},
        timeout=10,
    ).raise_for_status()


def mark_message_read(user_id: str, message_id: str) -> None:
    """Marks a message as read."""
    requests.patch(
        f"{BASE_URL}/users/{user_id}/messages/{message_id}",
        headers=HEADERS,
        json={"isRead": True},
        timeout=10,
    ).raise_for_status()


class EmailFollowUpController(guava.CallController):
    def __init__(
        self,
        contact_name: str,
        user_id: str,
        message_id: str,
    ):
        super().__init__()
        self.contact_name = contact_name
        self.user_id = user_id
        self.message_id = message_id
        self.subject = ""
        self.body_preview = ""
        self.received_date = ""

        # Fetch the email details before the call so the agent has full context
        try:
            msg = get_message(user_id, message_id)
            self.subject = msg.get("subject") or "(no subject)"
            self.body_preview = msg.get("bodyPreview") or ""
            received_raw = msg.get("receivedDateTime", "")
            if received_raw:
                try:
                    dt = datetime.fromisoformat(received_raw.replace("Z", "+00:00"))
                    self.received_date = dt.strftime("%B %-d")
                except (ValueError, AttributeError):
                    self.received_date = received_raw
            logging.info(
                "Email fetched — subject: '%s', received: %s", self.subject, self.received_date
            )
        except Exception as e:
            logging.error("Failed to fetch email %s for user %s: %s", message_id, user_id, e)

        self.set_persona(
            organization_name="Meridian Partners",
            agent_name="Sam",
            agent_purpose=(
                "to follow up with contacts about emails that require a response or decision"
            ),
        )

        self.reach_person(
            contact_full_name=contact_name,
            on_success=self.begin_follow_up,
            on_failure=self.recipient_unavailable,
        )

    def begin_follow_up(self):
        subject_note = f" regarding '{self.subject}'" if self.subject else ""
        date_note = f" that was sent on {self.received_date}" if self.received_date else ""
        preview_note = (
            f" The email reads: {self.body_preview[:300]}"
            if self.body_preview
            else ""
        )

        self.set_task(
            objective=(
                f"Follow up with {self.contact_name} about an email{subject_note}{date_note}. "
                "Understand their response and record any action items."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.contact_name}, this is Sam calling from Meridian Partners. "
                    f"I'm reaching out to follow up on an email{subject_note}{date_note}."
                ),
                guava.Field(
                    key="received_email",
                    field_type="multiple_choice",
                    description=(
                        f"Ask if they received and had a chance to review "
                        f"the email about '{self.subject}'."
                    ),
                    choices=["yes, I've reviewed it", "I received it but haven't reviewed it", "I didn't receive it"],
                    required=True,
                ),
                guava.Field(
                    key="response_or_action",
                    field_type="text",
                    description=(
                        "Ask for their response, decision, or any questions they have. "
                        "If they haven't reviewed it, ask when they expect to. "
                        "Capture their answer."
                    ),
                    required=True,
                ),
            ],
            on_complete=self.handle_response,
        )

    def handle_response(self):
        received = self.get_field("received_email") or ""
        response = self.get_field("response_or_action") or ""

        logging.info(
            "Follow-up outcome for %s — received: %s, response: %s",
            self.contact_name, received, response,
        )

        # Mark the email as read since we've followed up
        try:
            mark_message_read(self.user_id, self.message_id)
            logging.info("Message %s marked as read", self.message_id)
        except Exception as e:
            logging.warning("Could not mark message as read: %s", e)

        if "reviewed" in received and response:
            self.hangup(
                final_instructions=(
                    f"Thank {self.contact_name} for their time. "
                    f"Confirm you've noted their response: '{response}'. "
                    "Let them know our team will follow up by email with next steps. "
                    "Wish them a great day."
                )
            )
        elif "haven't reviewed" in received:
            # Flag the email for re-follow-up
            try:
                flag_message(self.user_id, self.message_id)
                logging.info("Message %s flagged for re-follow-up", self.message_id)
            except Exception as e:
                logging.warning("Could not flag message: %s", e)

            self.hangup(
                final_instructions=(
                    f"Thank {self.contact_name} for letting us know. "
                    "Let them know our team will follow up again once they've had a chance to review. "
                    "If they have any questions in the meantime, they can reply to the email. "
                    "Wish them well."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    f"Let {self.contact_name} know we'll resend the email and follow up again shortly. "
                    "Apologize for any inconvenience. Thank them for their time."
                )
            )

    def recipient_unavailable(self):
        logging.info("Unable to reach %s for email follow-up", self.contact_name)
        subject_note = f" regarding '{self.subject}'" if self.subject else ""
        self.hangup(
            final_instructions=(
                f"Leave a brief voicemail for {self.contact_name} from Meridian Partners. "
                f"Let them know you're calling to follow up on an email{subject_note} "
                "and ask them to reply at their earliest convenience or call back. "
                "Keep it professional and brief."
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Outbound follow-up call about a specific Outlook email."
    )
    parser.add_argument("phone", help="Contact's phone number (E.164, e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Contact's full name")
    parser.add_argument("--user-id", required=True, help="Mailbox user ID or email (UPN)")
    parser.add_argument("--message-id", required=True, help="Graph message ID to follow up on")
    args = parser.parse_args()

    logging.info(
        "Initiating email follow-up call to %s (%s) for message %s",
        args.name, args.phone, args.message_id,
    )

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=EmailFollowUpController(
            contact_name=args.name,
            user_id=args.user_id,
            message_id=args.message_id,
        ),
    )

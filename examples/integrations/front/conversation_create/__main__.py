import guava
import os
import logging
import requests
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)

FRONT_API_TOKEN = os.environ["FRONT_API_TOKEN"]
FRONT_INBOX_ID = os.environ["FRONT_INBOX_ID"]  # e.g. "inb_XXXX"

BASE_URL = "https://api2.frontapp.com"
HEADERS = {
    "Authorization": f"Bearer {FRONT_API_TOKEN}",
    "Content-Type": "application/json",
}


def find_contact(email: str) -> dict | None:
    """Searches Front for a contact by email. Returns the contact or None."""
    resp = requests.get(
        f"{BASE_URL}/contacts",
        headers=HEADERS,
        params={"q[handles][handle]": email, "q[handles][source]": "email"},
        timeout=10,
    )
    resp.raise_for_status()
    results = resp.json().get("_results", [])
    return results[0] if results else None


def create_conversation(
    inbox_id: str,
    sender_name: str,
    sender_email: str,
    subject: str,
    body: str,
) -> dict:
    """Creates a new inbound message/conversation in the specified Front inbox."""
    payload = {
        "sender": {
            "name": sender_name,
            "handle": sender_email,
        },
        "subject": subject,
        "body": body,
        "metadata": {
            "is_inbound": True,
        },
        "tags": ["voice", "guava"],
    }
    resp = requests.post(
        f"{BASE_URL}/channels/{inbox_id}/incoming_messages",
        headers=HEADERS,
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


class ConversationCreateController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Relay Agency",
            agent_name="Morgan",
            agent_purpose=(
                "to help Relay Agency customers get their inquiries logged and routed to "
                "the right team member via Front"
            ),
        )

        self.set_task(
            objective=(
                "A customer has called Relay Agency. Collect their contact details and the "
                "nature of their inquiry, then create a conversation in Front so the right "
                "team member can follow up."
            ),
            checklist=[
                guava.Say(
                    "Thank you for calling Relay Agency. I'm Morgan. "
                    "I'll take your details and make sure this gets to the right person on our team."
                ),
                guava.Field(
                    key="caller_name",
                    field_type="text",
                    description="Ask for the caller's full name.",
                    required=True,
                ),
                guava.Field(
                    key="caller_email",
                    field_type="text",
                    description="Ask for their email address.",
                    required=True,
                ),
                guava.Field(
                    key="inquiry_type",
                    field_type="multiple_choice",
                    description="Ask what their inquiry is about.",
                    choices=[
                        "new project inquiry",
                        "existing project question",
                        "billing or invoice",
                        "partnership or referral",
                        "general question",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="inquiry_detail",
                    field_type="text",
                    description=(
                        "Ask them to describe their inquiry. "
                        "Capture enough detail for the team to follow up effectively."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="urgency",
                    field_type="multiple_choice",
                    description="Ask how urgently they need a response.",
                    choices=["asap", "within a day or two", "no rush"],
                    required=False,
                ),
            ],
            on_complete=self.create_front_conversation,
        )

        self.accept_call()

    def create_front_conversation(self):
        name = self.get_field("caller_name") or "Unknown"
        email = self.get_field("caller_email") or ""
        inquiry_type = self.get_field("inquiry_type") or "general question"
        detail = self.get_field("inquiry_detail") or ""
        urgency = self.get_field("urgency") or "within a day or two"

        subject = f"[{inquiry_type.title()}] Inbound call from {name}"
        body = (
            f"<p>Caller: {name}<br>Email: {email}</p>"
            f"<p><strong>Inquiry type:</strong> {inquiry_type}</p>"
            f"<p><strong>Detail:</strong><br>{detail}</p>"
            f"<p><strong>Urgency:</strong> {urgency}</p>"
            f"<p><em>Received via voice — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</em></p>"
        )

        logging.info("Creating Front conversation for %s (%s) — type: %s", name, email, inquiry_type)
        try:
            result = create_conversation(FRONT_INBOX_ID, name, email, subject, body)
            conv_id = result.get("id", "")
            logging.info("Front conversation created: %s", conv_id)

            self.hangup(
                final_instructions=(
                    f"Let {name} know their inquiry has been logged and the right team member "
                    "will follow up via email. Based on the urgency they mentioned, set an "
                    "appropriate expectation — asap means within a few hours; a day or two is the "
                    "standard. Thank them for calling Relay Agency and wish them a great day."
                )
            )
        except Exception as e:
            logging.error("Failed to create Front conversation: %s", e)
            self.hangup(
                final_instructions=(
                    f"Apologize to {name} for a technical issue and let them know someone from the "
                    "team will be in touch via email within one business day. Thank them for their patience."
                )
            )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=ConversationCreateController,
    )

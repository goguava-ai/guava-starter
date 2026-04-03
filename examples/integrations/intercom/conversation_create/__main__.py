import guava
import os
import logging
import requests
from datetime import datetime

logging.basicConfig(level=logging.INFO)

INTERCOM_ACCESS_TOKEN = os.environ["INTERCOM_ACCESS_TOKEN"]

BASE_URL = "https://api.intercom.io"
HEADERS = {
    "Authorization": f"Bearer {INTERCOM_ACCESS_TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Intercom-Version": "2.10",
}


def find_or_create_contact(name: str, email: str) -> str:
    """Finds an existing Intercom contact by email or creates a new one. Returns the contact ID."""
    # Search first
    resp = requests.post(
        f"{BASE_URL}/contacts/search",
        headers=HEADERS,
        json={
            "query": {
                "operator": "AND",
                "value": [{"field": "email", "operator": "=", "value": email}],
            }
        },
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json().get("data", [])
    if data:
        return data[0]["id"]

    # Create new contact
    resp = requests.post(
        f"{BASE_URL}/contacts",
        headers=HEADERS,
        json={"role": "user", "email": email, "name": name},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["id"]


def create_conversation(contact_id: str, body: str) -> str:
    """Creates a new conversation in Intercom on behalf of the contact. Returns the conversation ID."""
    resp = requests.post(
        f"{BASE_URL}/conversations",
        headers=HEADERS,
        json={
            "from": {"type": "contact", "id": contact_id},
            "body": body,
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("conversation_id") or resp.json().get("id", "")


def add_note_to_conversation(conversation_id: str, note: str) -> None:
    """Adds an internal note to the conversation."""
    resp = requests.post(
        f"{BASE_URL}/conversations/{conversation_id}/parts",
        headers=HEADERS,
        json={"message_type": "note", "type": "admin", "body": note},
        timeout=10,
    )
    resp.raise_for_status()


class ConversationCreateController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Stackline",
            agent_name="Casey",
            agent_purpose=(
                "to help Stackline customers log their support requests and ensure "
                "they're captured in Intercom for follow-up"
            ),
        )

        self.set_task(
            objective=(
                "A customer has called Stackline with a support request. Collect their details, "
                "understand the issue, and create an Intercom conversation so the team can "
                "follow up in the right channel."
            ),
            checklist=[
                guava.Say(
                    "Thanks for calling Stackline Support. I'm Casey. "
                    "I'll log your request and make sure the right person follows up with you."
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
                    key="issue_type",
                    field_type="multiple_choice",
                    description="Ask what type of issue they're facing.",
                    choices=[
                        "technical issue",
                        "billing question",
                        "account access",
                        "feature request",
                        "general inquiry",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="issue_detail",
                    field_type="text",
                    description=(
                        "Ask them to describe their issue in detail. "
                        "Capture everything relevant so the team can follow up without callbacks."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="preferred_response",
                    field_type="multiple_choice",
                    description="Ask how they'd prefer to receive a response.",
                    choices=["email", "in-app message", "phone call back"],
                    required=True,
                ),
            ],
            on_complete=self.log_conversation,
        )

        self.accept_call()

    def log_conversation(self):
        name = self.get_field("caller_name") or "Unknown"
        email = self.get_field("caller_email") or ""
        issue_type = self.get_field("issue_type") or "general inquiry"
        detail = self.get_field("issue_detail") or ""
        response_pref = self.get_field("preferred_response") or "email"

        logging.info("Creating Intercom conversation for %s (%s) — type: %s", name, email, issue_type)

        contact_id = ""
        try:
            contact_id = find_or_create_contact(name, email)
            logging.info("Intercom contact: %s", contact_id)
        except Exception as e:
            logging.error("Failed to find/create Intercom contact: %s", e)

        if not contact_id:
            self.hangup(
                final_instructions=(
                    f"Apologize to {name} for a technical issue. Let them know their request has "
                    "been noted manually and someone will reach out via email. Thank them for their patience."
                )
            )
            return

        message_body = (
            f"Hi, I called in with a {issue_type}.\n\n{detail}\n\n"
            f"Preferred response: {response_pref}"
        )

        conv_id = ""
        try:
            conv_id = create_conversation(contact_id, message_body)
            logging.info("Intercom conversation created: %s", conv_id)
        except Exception as e:
            logging.error("Failed to create Intercom conversation: %s", e)

        if conv_id:
            try:
                note = (
                    f"[Voice call — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}]\n"
                    f"Caller: {name} | Email: {email}\n"
                    f"Issue type: {issue_type}\n"
                    f"Preferred response: {response_pref}"
                )
                add_note_to_conversation(conv_id, note)
                logging.info("Internal note added to conversation %s.", conv_id)
            except Exception as e:
                logging.warning("Could not add note to conversation %s: %s", conv_id, e)

        self.hangup(
            final_instructions=(
                f"Let {name} know their support request has been logged and the team will "
                f"follow up via {response_pref}. "
                + (f"Their conversation ID is {conv_id}. " if conv_id else "")
                + "Thank them for calling Stackline and wish them a great day."
            )
        )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=ConversationCreateController,
    )

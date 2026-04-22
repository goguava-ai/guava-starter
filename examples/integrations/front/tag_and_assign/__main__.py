import guava
import os
import logging
from guava import logging_utils
import requests
from datetime import datetime, timezone


FRONT_API_TOKEN = os.environ["FRONT_API_TOKEN"]
FRONT_INBOX_ID = os.environ["FRONT_INBOX_ID"]

BASE_URL = "https://api2.frontapp.com"
HEADERS = {
    "Authorization": f"Bearer {FRONT_API_TOKEN}",
    "Content-Type": "application/json",
}

# Map categories to Front teammate IDs or group IDs for assignment.
# Set these in environment variables for flexibility.
ROUTING_MAP = {
    "billing": os.environ.get("FRONT_TEAMMATE_BILLING", ""),
    "technical support": os.environ.get("FRONT_TEAMMATE_TECH", ""),
    "account management": os.environ.get("FRONT_TEAMMATE_AM", ""),
    "sales": os.environ.get("FRONT_TEAMMATE_SALES", ""),
    "general": os.environ.get("FRONT_TEAMMATE_GENERAL", ""),
}


def create_conversation(inbox_id: str, sender_name: str, sender_email: str, subject: str, body: str) -> str:
    """Creates a conversation and returns its ID."""
    payload = {
        "sender": {"name": sender_name, "handle": sender_email},
        "subject": subject,
        "body": body,
        "metadata": {"is_inbound": True},
        "tags": ["voice", "guava"],
    }
    resp = requests.post(
        f"{BASE_URL}/channels/{inbox_id}/incoming_messages",
        headers=HEADERS,
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("id", "")


def apply_tag(conversation_id: str, tag_id: str) -> None:
    requests.post(
        f"{BASE_URL}/conversations/{conversation_id}/tags",
        headers=HEADERS,
        json={"tag_ids": [tag_id]},
        timeout=10,
    ).raise_for_status()


def assign_conversation(conversation_id: str, assignee_id: str) -> None:
    """Assigns the conversation to a teammate."""
    requests.patch(
        f"{BASE_URL}/conversations/{conversation_id}",
        headers=HEADERS,
        json={"assignee_id": assignee_id},
        timeout=10,
    ).raise_for_status()


def get_or_create_tag(tag_name: str) -> str:
    """Returns tag ID, creating the tag if it doesn't exist."""
    # List tags and search
    resp = requests.get(f"{BASE_URL}/tags", headers=HEADERS, timeout=10)
    resp.raise_for_status()
    for tag in resp.json().get("_results", []):
        if tag.get("name", "").lower() == tag_name.lower():
            return tag["id"]
    # Create
    resp = requests.post(f"{BASE_URL}/tags", headers=HEADERS, json={"name": tag_name}, timeout=10)
    resp.raise_for_status()
    return resp.json()["id"]


class TagAndAssignController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Relay Agency",
            agent_name="Morgan",
            agent_purpose=(
                "to triage inbound calls at Relay Agency, capture the customer's issue, "
                "and route the conversation to the right teammate in Front"
            ),
        )

        self.set_task(
            objective=(
                "A customer has called Relay Agency. Understand their issue, create a Front "
                "conversation, apply the appropriate tags, and assign it to the right teammate."
            ),
            checklist=[
                guava.Say(
                    "Thanks for calling Relay Agency. I'm Morgan — I'll get you connected "
                    "with the right person. Let me grab a few details first."
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
                    key="category",
                    field_type="multiple_choice",
                    description="Ask what their inquiry is about.",
                    choices=[
                        "billing",
                        "technical support",
                        "account management",
                        "sales",
                        "general",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="issue_summary",
                    field_type="text",
                    description="Ask for a brief summary of their question or issue.",
                    required=True,
                ),
                guava.Field(
                    key="urgency",
                    field_type="multiple_choice",
                    description="Ask how urgent this is.",
                    choices=["urgent", "normal", "low priority"],
                    required=True,
                ),
            ],
            on_complete=self.route_to_front,
        )

        self.accept_call()

    def route_to_front(self):
        name = self.get_field("caller_name") or "Unknown"
        email = self.get_field("caller_email") or ""
        category = self.get_field("category") or "general"
        summary = self.get_field("issue_summary") or ""
        urgency = self.get_field("urgency") or "normal"

        subject = f"[{category.title()}] {summary[:80]}"
        body = (
            f"<p>Caller: {name}<br>Email: {email}</p>"
            f"<p><strong>Category:</strong> {category}<br>"
            f"<strong>Urgency:</strong> {urgency}</p>"
            f"<p><strong>Summary:</strong><br>{summary}</p>"
            f"<p><em>Via voice — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</em></p>"
        )

        logging.info("Creating Front conversation for %s — category: %s, urgency: %s", name, category, urgency)

        conv_id = ""
        try:
            conv_id = create_conversation(FRONT_INBOX_ID, name, email, subject, body)
            logging.info("Front conversation created: %s", conv_id)
        except Exception as e:
            logging.error("Failed to create Front conversation: %s", e)

        if conv_id:
            # Apply urgency and category tags
            for tag_name in [category, urgency, "voice"]:
                try:
                    tag_id = get_or_create_tag(tag_name)
                    apply_tag(conv_id, tag_id)
                except Exception as e:
                    logging.warning("Could not apply tag '%s': %s", tag_name, e)

            # Assign to the right teammate
            assignee_id = ROUTING_MAP.get(category, "")
            if assignee_id:
                try:
                    assign_conversation(conv_id, assignee_id)
                    logging.info("Conversation %s assigned to %s.", conv_id, assignee_id)
                except Exception as e:
                    logging.error("Failed to assign conversation %s: %s", conv_id, e)

        self.hangup(
            final_instructions=(
                f"Let {name} know their inquiry has been logged and routed to the {category} team. "
                + ("Given the urgency they indicated, let them know the team will prioritize their request. "
                   if urgency == "urgent" else "")
                + "Let them know they'll receive a reply via email. "
                "Thank them for calling Relay Agency and wish them a great day."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=TagAndAssignController,
    )

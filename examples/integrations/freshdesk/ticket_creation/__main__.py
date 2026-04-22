import logging
import os

import guava
import requests
from guava import logging_utils

FRESHDESK_DOMAIN = os.environ["FRESHDESK_DOMAIN"]  # e.g. "mycompany"
FRESHDESK_API_KEY = os.environ["FRESHDESK_API_KEY"]

BASE_URL = f"https://{FRESHDESK_DOMAIN}.freshdesk.com/api/v2"
# Freshdesk uses API key as the username and "X" as the password.
AUTH = (FRESHDESK_API_KEY, "X")

PRIORITY_MAP = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "urgent": 4,
}

SOURCE_PHONE = 3  # Freshdesk source ID for Phone


def create_ticket(
    name: str,
    email: str,
    subject: str,
    description: str,
    priority: int,
    tags: list[str] | None = None,
) -> dict:
    """Creates a new Freshdesk ticket. Returns the created ticket object."""
    payload = {
        "name": name,
        "email": email,
        "subject": subject,
        "description": description,
        "status": 2,  # Open
        "priority": priority,
        "source": SOURCE_PHONE,
        "tags": tags or ["guava", "voice"],
    }
    resp = requests.post(
        f"{BASE_URL}/tickets",
        auth=AUTH,
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


agent = guava.Agent(
    name="Jordan",
    organization="Luminary Cloud",
    purpose=(
        "to help Luminary Cloud customers report issues and open support tickets "
        "so the right team can follow up promptly"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "open_ticket",
        objective=(
            "A customer has called Luminary Cloud support. Greet them empathetically, "
            "collect their contact details and a description of their issue, and open "
            "a Freshdesk support ticket."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling Luminary Cloud Support. I'm Jordan — sorry to hear "
                "you're having an issue. Let me get some details so I can open a ticket "
                "for you right away."
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
                description="Ask what type of issue they're experiencing.",
                choices=[
                    "service outage",
                    "performance degradation",
                    "configuration problem",
                    "billing issue",
                    "feature question",
                    "other",
                ],
                required=True,
            ),
            guava.Field(
                key="issue_summary",
                field_type="text",
                description="Ask for a brief description of the issue.",
                required=True,
            ),
            guava.Field(
                key="issue_detail",
                field_type="text",
                description=(
                    "Ask for more detail — what were they doing when it happened, "
                    "are there any error messages, and how long has it been occurring?"
                ),
                required=False,
            ),
            guava.Field(
                key="priority",
                field_type="multiple_choice",
                description="Ask how urgently this is affecting their work.",
                choices=["low", "medium", "high", "urgent"],
                required=True,
            ),
        ],
    )


@agent.on_task_complete("open_ticket")
def on_done(call: guava.Call) -> None:
    name = call.get_field("caller_name") or "Unknown"
    email = call.get_field("caller_email") or ""
    issue_type = call.get_field("issue_type") or "other"
    summary = call.get_field("issue_summary") or "Support request"
    detail = call.get_field("issue_detail") or ""
    priority_label = call.get_field("priority") or "medium"

    priority = PRIORITY_MAP.get(priority_label, 2)
    subject = f"[{issue_type.title()}] {summary}"
    description = summary + (f"<br><br><b>Additional detail:</b><br>{detail}" if detail else "")

    logging.info("Creating Freshdesk ticket for %s (%s) — priority: %s", name, email, priority_label)
    try:
        ticket = create_ticket(name, email, subject, description, priority, tags=["guava", "voice", issue_type])
        ticket_id = ticket.get("id", "")
        logging.info("Freshdesk ticket created: #%s", ticket_id)

        call.hangup(
            final_instructions=(
                f"Let {name} know their support ticket has been created. "
                + (f"Their ticket number is #{ticket_id}. " if ticket_id else "")
                + "They'll receive a confirmation email shortly and a support agent will "
                "follow up based on the priority they selected. "
                "Thank them for calling Luminary Cloud."
            )
        )
    except Exception as e:
        logging.error("Failed to create Freshdesk ticket: %s", e)
        call.hangup(
            final_instructions=(
                f"Apologize to {name} for a brief technical issue. Ask them to email "
                "support@luminarycloud.com with the details they shared, or try calling "
                "back shortly. Thank them for their patience."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])

import guava
import os
import logging
from guava import logging_utils
import requests


ACCESS_TOKEN = os.environ["ZOHO_DESK_ACCESS_TOKEN"]
ORG_ID = os.environ["ZOHO_DESK_ORG_ID"]
HEADERS = {
    "Authorization": f"Zoho-oauthtoken {ACCESS_TOKEN}",
    "orgId": ORG_ID,
    "Content-Type": "application/json",
}
BASE_URL = "https://desk.zoho.com/api/v1"


def create_ticket(
    subject: str,
    description: str,
    contact_name: str,
    contact_email: str,
    priority: str,
) -> dict:
    """Creates a new Zoho Desk support ticket and returns the created ticket object."""
    payload = {
        "subject": subject,
        "description": description,
        "contact": {
            "email": contact_email,
            "lastName": contact_name,
        },
        "priority": priority,
        "channel": "Voice",
        "status": "Open",
        "tags": [{"name": "guava"}, {"name": "voice"}],
    }
    resp = requests.post(f"{BASE_URL}/tickets", headers=HEADERS, json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json()


agent = guava.Agent(
    name="Jordan",
    organization="Clearline Software",
    purpose="to help customers report issues and open support tickets with Clearline Software",
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "open_ticket",
        objective=(
            "A customer has called Clearline Software support. Greet them, collect their "
            "contact information, the type of issue they're experiencing, and a clear "
            "description of their problem so we can open a support ticket."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling Clearline Software support. My name is Jordan. "
                "I'm here to help you today. I'll collect some information and open a "
                "support ticket for you right away."
            ),
            guava.Field(
                key="caller_name",
                field_type="text",
                description="Ask the caller for their full name.",
                required=True,
            ),
            guava.Field(
                key="caller_email",
                field_type="text",
                description="Ask for their email address so we can send ticket updates.",
                required=True,
            ),
            guava.Field(
                key="issue_type",
                field_type="multiple_choice",
                description=(
                    "Ask what type of issue they're experiencing. "
                    "Map their answer to one of the available categories."
                ),
                choices=[
                    "billing",
                    "technical-issue",
                    "account-access",
                    "feature-request",
                    "other",
                ],
                required=True,
            ),
            guava.Field(
                key="issue_summary",
                field_type="text",
                description=(
                    "Ask the caller to briefly describe the issue they're experiencing. "
                    "Capture a clear one-sentence summary."
                ),
                required=True,
            ),
            guava.Field(
                key="issue_detail",
                field_type="text",
                description=(
                    "Ask for any additional details — what they were doing when it happened, "
                    "any error messages they saw, and how long it has been occurring. "
                    "This is optional; if they have nothing to add, move on."
                ),
                required=False,
            ),
            guava.Field(
                key="priority",
                field_type="multiple_choice",
                description=(
                    "Ask how urgently this is affecting their work. "
                    "Map their answer to a priority level."
                ),
                choices=["low", "medium", "high", "urgent"],
                required=True,
            ),
        ],
    )


@agent.on_task_complete("open_ticket")
def on_done(call: guava.Call) -> None:
    name = call.get_field("caller_name") or "Unknown Caller"
    email = call.get_field("caller_email") or ""
    issue_type = call.get_field("issue_type") or "other"
    summary = call.get_field("issue_summary") or "Support request"
    detail = call.get_field("issue_detail") or ""
    priority = call.get_field("priority") or "Medium"

    # Capitalize priority to match Zoho Desk API values
    priority_map = {
        "low": "Low",
        "medium": "Medium",
        "high": "High",
        "urgent": "Urgent",
    }
    priority_value = priority_map.get(priority.lower(), "Medium")

    subject = f"[{issue_type.replace('-', ' ').title()}] {summary}"
    description = summary
    if detail:
        description = f"{summary}\n\nAdditional details:\n{detail}"

    logging.info(
        "Creating Zoho Desk ticket for %s (%s) — type: %s, priority: %s",
        name, email, issue_type, priority_value,
    )
    try:
        ticket = create_ticket(
            subject=subject,
            description=description,
            contact_name=name,
            contact_email=email,
            priority=priority_value,
        )
        ticket_number = ticket.get("ticketNumber") or ticket.get("id")
        logging.info("Zoho Desk ticket created: #%s", ticket_number)

        call.hangup(
            final_instructions=(
                f"Let {name} know their support ticket has been created successfully. "
                f"Their ticket number is {ticket_number}. "
                "Tell them they'll receive a confirmation email shortly and our team will "
                "be in touch based on the priority they selected. "
                "Thank them for calling Clearline Software."
            )
        )
    except Exception as e:
        logging.error("Failed to create Zoho Desk ticket: %s", e)
        call.hangup(
            final_instructions=(
                f"Apologize to {name} for a technical issue and let them know a support "
                "agent will follow up with them by email to manually open their ticket. "
                "Thank them for their patience."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])

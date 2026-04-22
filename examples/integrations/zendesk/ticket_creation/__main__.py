import guava
import os
import logging
from guava import logging_utils
import base64
import requests


ZENDESK_SUBDOMAIN = os.environ["ZENDESK_SUBDOMAIN"]
ZENDESK_EMAIL = os.environ["ZENDESK_EMAIL"]
ZENDESK_API_TOKEN = os.environ["ZENDESK_API_TOKEN"]

_encoded = base64.b64encode(f"{ZENDESK_EMAIL}/token:{ZENDESK_API_TOKEN}".encode()).decode()
HEADERS = {
    "Authorization": f"Basic {_encoded}",
    "Content-Type": "application/json",
}
BASE_URL = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com/api/v2"


def create_ticket(subject: str, body: str, requester_name: str, requester_email: str, priority: str) -> dict:
    """Creates a new Zendesk support ticket and returns the created ticket object."""
    payload = {
        "ticket": {
            "subject": subject,
            "comment": {"body": body},
            "requester": {"name": requester_name, "email": requester_email},
            "priority": priority,
            "tags": ["voice", "guava"],
        }
    }
    resp = requests.post(f"{BASE_URL}/tickets", headers=HEADERS, json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json()["ticket"]


agent = guava.Agent(
    name="Jordan",
    organization="Horizon Software",
    purpose="to help customers report issues and open support tickets with Horizon Software",
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "open_ticket",
        objective=(
            "A customer has called Horizon Software support. Greet them, collect their contact "
            "information and a clear description of their issue so we can open a support ticket."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling Horizon Software support. My name is Jordan. "
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
                    "any error messages they saw, and how long it has been occurring."
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
                choices=["low", "normal", "high", "urgent"],
                required=True,
            ),
        ],
    )


@agent.on_task_complete("open_ticket")
def on_done(call: guava.Call) -> None:
    name = call.get_field("caller_name") or "Unknown Caller"
    email = call.get_field("caller_email")
    summary = call.get_field("issue_summary") or "Support request"
    detail = call.get_field("issue_detail") or ""
    priority = call.get_field("priority") or "normal"

    body = summary
    if detail:
        body = f"{summary}\n\nAdditional details:\n{detail}"

    logging.info("Creating Zendesk ticket for %s (%s) — priority: %s", name, email, priority)
    try:
        ticket = create_ticket(
            subject=summary,
            body=body,
            requester_name=name,
            requester_email=email,
            priority=priority,
        )
        ticket_id = ticket["id"]
        logging.info("Zendesk ticket created: #%s", ticket_id)

        call.hangup(
            final_instructions=(
                f"Let {name} know their support ticket has been created successfully. "
                f"Their ticket number is {ticket_id}. "
                "Tell them they'll receive a confirmation email shortly and our team will "
                "be in touch based on the priority they selected. "
                "Thank them for calling Horizon Software."
            )
        )
    except Exception as e:
        logging.error("Failed to create Zendesk ticket: %s", e)
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

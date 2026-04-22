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


def get_ticket(ticket_id: str) -> dict | None:
    """Fetches a single Zendesk ticket by ID."""
    resp = requests.get(f"{BASE_URL}/tickets/{ticket_id}", headers=HEADERS, timeout=10)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()["ticket"]


def add_comment(ticket_id: str, comment_body: str, public: bool = True) -> dict:
    """
    Adds a comment to an existing ticket.
    public=True makes it visible to the requester; public=False is an internal agent note.
    Returns the updated ticket.
    """
    payload = {
        "ticket": {
            "comment": {
                "body": comment_body,
                "public": public,
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
    return resp.json()["ticket"]


agent = guava.Agent(
    name="Jordan",
    organization="Horizon Software",
    purpose="to help customers add information to an existing support ticket",
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "verify_ticket",
        objective=(
            "A customer has called to provide additional information on an open support ticket. "
            "Collect their ticket number and verify it, then gather the update they want to add."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling Horizon Software support. My name is Jordan. "
                "I can add information to an existing support ticket for you."
            ),
            guava.Field(
                key="ticket_id",
                field_type="text",
                description=(
                    "Ask for the ticket number they'd like to update. Capture digits only."
                ),
                required=True,
            ),
            guava.Field(
                key="caller_name",
                field_type="text",
                description="Ask for their name so we can note who called in with the update.",
                required=True,
            ),
        ],
    )


@agent.on_task_complete("verify_ticket")
def on_verify_ticket_done(call: guava.Call) -> None:
    ticket_id = (call.get_field("ticket_id") or "").replace("#", "").strip()
    caller_name = call.get_field("caller_name") or "Unknown Caller"

    if not ticket_id.isdigit():
        call.hangup(
            final_instructions=(
                f"Let {caller_name} know the ticket number they provided doesn't appear to be "
                "valid. Ask them to check their confirmation email for the correct number and "
                "call back. Thank them for calling."
            )
        )
        return

    logging.info("Looking up ticket #%s for update", ticket_id)
    try:
        ticket = get_ticket(ticket_id)
    except Exception as e:
        logging.error("Failed to fetch ticket #%s: %s", ticket_id, e)
        ticket = None

    if not ticket:
        call.hangup(
            final_instructions=(
                f"Let {caller_name} know we could not find ticket #{ticket_id}. "
                "Ask them to double-check the number from their confirmation email. "
                "Thank them for calling."
            )
        )
        return

    if ticket.get("status") in ("solved", "closed"):
        call.hangup(
            final_instructions=(
                f"Let {caller_name} know that ticket #{ticket_id} is already "
                f"{ticket['status']} and can no longer be updated. "
                "If the issue has recurred, suggest they call back to open a new ticket. "
                "Thank them for calling."
            )
        )
        return

    # Store the verified ticket ID for use in the next task
    call.verified_ticket_id = ticket_id
    call.verified_ticket_subject = ticket.get("subject", "their issue")

    subject = ticket.get("subject", "their issue")
    call.set_task(
        "post_update",
        objective=f"Collect the update {caller_name} wants to add to ticket #{ticket_id} about '{subject}'.",
        checklist=[
            guava.Say(
                f"I found ticket #{ticket_id}: '{subject}'. "
                "What information would you like to add to this ticket?"
            ),
            guava.Field(
                key="update_text",
                field_type="text",
                description=(
                    "Listen carefully and capture everything the caller wants to add to their "
                    "ticket — new symptoms, steps they've tried, error messages, or any other "
                    "relevant details. Capture their full message."
                ),
                required=True,
            ),
            guava.Field(
                key="issue_resolved",
                field_type="multiple_choice",
                description=(
                    "Ask if the issue has been resolved since they opened the ticket, "
                    "or if it is still ongoing."
                ),
                choices=["resolved", "still ongoing"],
                required=True,
            ),
        ],
    )


@agent.on_task_complete("post_update")
def on_post_update_done(call: guava.Call) -> None:
    caller_name = call.get_field("caller_name") or "the caller"
    ticket_id = call.verified_ticket_id
    update_text = call.get_field("update_text") or ""
    issue_resolved = call.get_field("issue_resolved") or "still ongoing"

    comment_body = (
        f"Phone update from {caller_name}:\n\n"
        f"{update_text}\n\n"
        f"Issue status per caller: {issue_resolved}."
    )

    logging.info("Adding comment to ticket #%s", ticket_id)
    try:
        add_comment(ticket_id=str(ticket_id), comment_body=comment_body, public=True)
        logging.info("Comment added to ticket #%s", ticket_id)

        call.hangup(
            final_instructions=(
                f"Let {caller_name} know their update has been added to ticket #{ticket_id}. "
                "Our support team will review it and follow up by email. "
                + (
                    "Since they mentioned the issue is resolved, let them know they can reply "
                    "to the ticket email if it recurs. "
                    if issue_resolved == "resolved"
                    else ""
                )
                + "Thank them for calling Horizon Software."
            )
        )
    except Exception as e:
        logging.error("Failed to add comment to ticket #%s: %s", ticket_id, e)
        call.hangup(
            final_instructions=(
                f"Apologize to {caller_name} for a technical issue and let them know they can "
                "reply directly to the ticket confirmation email to add their update. "
                "Thank them for their patience."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])

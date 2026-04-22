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


def get_ticket(ticket_id: str) -> dict | None:
    """Fetches a single Zoho Desk ticket by ID. Returns the ticket object or None."""
    resp = requests.get(f"{BASE_URL}/tickets/{ticket_id}", headers=HEADERS, timeout=10)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def add_comment(ticket_id: str, content: str, is_public: bool = True) -> dict:
    """
    Posts a comment to an existing Zoho Desk ticket.
    is_public=True makes it visible to the customer; is_public=False is an internal note.
    Returns the created comment object.
    """
    payload = {
        "content": content,
        "isPublic": is_public,
    }
    resp = requests.post(
        f"{BASE_URL}/tickets/{ticket_id}/comments",
        headers=HEADERS,
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


agent = guava.Agent(
    name="Alex",
    organization="Clearline Software",
    purpose="to help customers add information to an existing support ticket",
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "verify_and_update",
        objective=(
            "A customer has called to provide additional information on an existing support ticket. "
            "Collect their ticket ID and email to verify ownership, then gather the update "
            "they want to add."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling Clearline Software support. My name is Alex. "
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
                key="caller_email",
                field_type="text",
                description=(
                    "Ask for the email address associated with the ticket "
                    "so we can verify ownership."
                ),
                required=True,
            ),
            guava.Field(
                key="update_details",
                field_type="text",
                description=(
                    "Ask what information they'd like to add to the ticket — new symptoms, "
                    "steps they've tried, error messages, or any other relevant details. "
                    "Capture their full message."
                ),
                required=True,
            ),
            guava.Field(
                key="update_type",
                field_type="multiple_choice",
                description=(
                    "Ask what type of update this is — are they providing new information, "
                    "requesting a status update, requesting escalation, or something else?"
                ),
                choices=[
                    "new-information",
                    "request-status-update",
                    "request-escalation",
                    "other",
                ],
                required=True,
            ),
        ],
    )


@agent.on_task_complete("verify_and_update")
def on_done(call: guava.Call) -> None:
    ticket_id = (call.get_field("ticket_id") or "").replace("#", "").strip()
    caller_email = (call.get_field("caller_email") or "").strip().lower()
    update_details = call.get_field("update_details") or ""
    update_type = call.get_field("update_type") or "new-information"

    if not ticket_id:
        call.hangup(
            final_instructions=(
                "Let the caller know the ticket number they provided doesn't appear to be valid. "
                "Ask them to check their confirmation email for the correct number and call back. "
                "Thank them for calling."
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
                f"Let the caller know we could not find ticket #{ticket_id}. "
                "Ask them to double-check the number from their confirmation email. "
                "Thank them for calling."
            )
        )
        return

    # Verify email ownership
    ticket_contact = ticket.get("contact") or {}
    ticket_email = (ticket_contact.get("email") or "").strip().lower()
    if ticket_email and caller_email and ticket_email != caller_email:
        logging.warning(
            "Email mismatch for ticket #%s: caller=%s, ticket=%s",
            ticket_id, caller_email, ticket_email,
        )
        call.hangup(
            final_instructions=(
                f"Let the caller know the email address they provided does not match "
                f"the one on file for ticket #{ticket_id}. "
                "For security, we can only update tickets when the email matches. "
                "Ask them to call back with the email address they used when opening the ticket. "
                "Thank them for calling."
            )
        )
        return

    ticket_status = ticket.get("status", "Open")
    if ticket_status == "Closed":
        call.hangup(
            final_instructions=(
                f"Let the caller know that ticket #{ticket_id} is already closed. "
                "If their issue has recurred or they have a new concern, "
                "suggest they call back to open a new ticket. "
                "Thank them for calling."
            )
        )
        return

    subject = ticket.get("subject", "their issue")
    ticket_number = ticket.get("ticketNumber") or ticket_id
    update_type_label = update_type.replace("-", " ").title()

    comment_content = (
        f"Phone update from customer (email: {caller_email}):\n\n"
        f"Update type: {update_type_label}\n\n"
        f"{update_details}"
    )

    logging.info(
        "Adding public comment to ticket #%s (type: %s)", ticket_id, update_type
    )
    try:
        add_comment(ticket_id=ticket_id, content=comment_content, is_public=True)
        logging.info("Comment added to ticket #%s", ticket_id)

        escalation_note = (
            " I've also flagged this as a request for escalation — "
            "a senior support engineer will review it shortly."
            if update_type == "request-escalation"
            else ""
        )

        call.hangup(
            final_instructions=(
                f"Let the caller know their update has been added to ticket #{ticket_number} "
                f"regarding '{subject}'.{escalation_note} "
                "Our support team will review it and follow up by email. "
                "Thank them for calling Clearline Software."
            )
        )
    except Exception as e:
        logging.error("Failed to add comment to ticket #%s: %s", ticket_id, e)
        call.hangup(
            final_instructions=(
                "Apologize for a technical issue and let the caller know they can reply "
                "directly to their ticket confirmation email to add the update. "
                "Thank them for their patience."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])

import base64
import logging
import os

import guava
import requests
from guava import logging_utils

ZENDESK_SUBDOMAIN = os.environ["ZENDESK_SUBDOMAIN"]
ZENDESK_EMAIL = os.environ["ZENDESK_EMAIL"]
ZENDESK_API_TOKEN = os.environ["ZENDESK_API_TOKEN"]

_encoded = base64.b64encode(f"{ZENDESK_EMAIL}/token:{ZENDESK_API_TOKEN}".encode()).decode()
HEADERS = {
    "Authorization": f"Basic {_encoded}",
    "Content-Type": "application/json",
}
BASE_URL = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com/api/v2"

STATUS_DESCRIPTIONS = {
    "new": "new and has not been assigned to an agent yet",
    "open": "open and being worked on by our support team",
    "pending": "pending — we are waiting for additional information from you",
    "hold": "on hold while we investigate further",
    "solved": "solved",
    "closed": "closed",
}

PRIORITY_DESCRIPTIONS = {
    "low": "low",
    "normal": "normal",
    "high": "high",
    "urgent": "urgent",
}


def find_user_by_email(email: str) -> dict | None:
    """Searches Zendesk for a user by email address. Returns the user object or None."""
    resp = requests.get(
        f"{BASE_URL}/users/search",
        headers=HEADERS,
        params={"query": email},
        timeout=10,
    )
    resp.raise_for_status()
    results = resp.json().get("results", [])
    return results[0] if results else None


def get_ticket(ticket_id: str) -> dict | None:
    """Fetches a single Zendesk ticket by ID. Returns the ticket object or None."""
    resp = requests.get(f"{BASE_URL}/tickets/{ticket_id}", headers=HEADERS, timeout=10)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()["ticket"]


def get_user_tickets(user_id: int) -> list[dict]:
    """Returns the most recent open/pending tickets for a user."""
    resp = requests.get(
        f"{BASE_URL}/users/{user_id}/tickets/requested",
        headers=HEADERS,
        params={"sort_by": "updated_at", "sort_order": "desc", "per_page": "5"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("tickets", [])


agent = guava.Agent(
    name="Jordan",
    organization="Horizon Software",
    purpose="to help customers check the status of their open support tickets",
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "lookup_ticket",
        objective=(
            "A customer has called to check on a support ticket. Collect their email "
            "and ticket ID (if they have it) so we can look up their case."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling Horizon Software support. My name is Jordan. "
                "I can help you check the status of a support ticket."
            ),
            guava.Field(
                key="caller_email",
                field_type="text",
                description="Ask for the email address associated with their support account.",
                required=True,
            ),
            guava.Field(
                key="ticket_id",
                field_type="text",
                description=(
                    "Ask if they have a ticket number. If yes, capture it as digits only. "
                    "If they don't have one, that's okay — capture 'none'."
                ),
                required=True,
            ),
        ],
    )


def _read_ticket_status(call: guava.Call, ticket: dict) -> None:
    ticket_id = ticket["id"]
    status = ticket.get("status", "unknown")
    subject = ticket.get("subject", "your issue")
    priority = ticket.get("priority", "normal")

    status_desc = STATUS_DESCRIPTIONS.get(status, status)
    priority_desc = PRIORITY_DESCRIPTIONS.get(priority, priority)

    logging.info(
        "Ticket #%s — status: %s, priority: %s, subject: %s",
        ticket_id, status, priority, subject,
    )

    call.hangup(
        final_instructions=(
            f"Tell the caller that ticket #{ticket_id} regarding '{subject}' is currently {status_desc}. "
            f"Its priority is {priority_desc}. "
            + (
                "Let them know our team will reach out by email once there is an update. "
                if status in ("new", "open", "hold")
                else (
                    "Since the ticket is pending, ask them to reply to the email our team sent "
                    "with the requested information so we can continue working on it. "
                    if status == "pending"
                    else "Let them know they can open a new ticket if the issue recurs. "
                )
            )
            + "Thank them for calling Horizon Software."
        )
    )


@agent.on_task_complete("lookup_ticket")
def on_done(call: guava.Call) -> None:
    caller_email = call.get_field("caller_email") or ""
    ticket_id_raw = call.get_field("ticket_id") or ""
    ticket_id = ticket_id_raw.strip().lower().replace("none", "").replace("#", "").strip()

    # Path A: caller provided a ticket ID — fetch it directly
    if ticket_id.isdigit():
        logging.info("Looking up ticket #%s", ticket_id)
        try:
            ticket = get_ticket(ticket_id)
        except Exception as e:
            logging.error("Failed to fetch ticket #%s: %s", ticket_id, e)
            ticket = None

        if ticket:
            _read_ticket_status(call, ticket)
            return

        # Ticket not found — fall through to email lookup
        logging.warning("Ticket #%s not found, falling back to email lookup", ticket_id)

    # Path B: look up by email and surface recent tickets
    logging.info("Searching for user by email: %s", caller_email)
    try:
        user = find_user_by_email(caller_email)
        if not user:
            call.hangup(
                final_instructions=(
                    "Let the caller know we were unable to find an account matching that email. "
                    "Suggest they double-check the address or contact support@horizonsoftware.com "
                    "directly. Thank them for calling."
                )
            )
            return

        tickets = get_user_tickets(user["id"])
        active = [t for t in tickets if t["status"] not in ("solved", "closed")]

        if not active:
            call.hangup(
                final_instructions=(
                    "Let the caller know there are no open or pending tickets associated with "
                    "their account. If they have a new issue to report, they can stay on the line "
                    "or call back and our team will open a new ticket. Thank them for calling."
                )
            )
            return

        # Surface the most recently updated open ticket
        ticket = active[0]
        _read_ticket_status(call, ticket)

    except Exception as e:
        logging.error("Failed to look up tickets by email: %s", e)
        call.hangup(
            final_instructions=(
                "Apologize for a technical issue and let the caller know they can check their "
                "ticket status at support.horizonsoftware.com or email support@horizonsoftware.com. "
                "Thank them for their patience."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])

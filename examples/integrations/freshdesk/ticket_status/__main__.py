import guava
import os
import logging
from guava import logging_utils
import requests


FRESHDESK_DOMAIN = os.environ["FRESHDESK_DOMAIN"]
FRESHDESK_API_KEY = os.environ["FRESHDESK_API_KEY"]

BASE_URL = f"https://{FRESHDESK_DOMAIN}.freshdesk.com/api/v2"
AUTH = (FRESHDESK_API_KEY, "X")

STATUS_LABELS = {
    2: "Open",
    3: "Pending",
    4: "Resolved",
    5: "Closed",
    6: "Waiting on Customer",
    7: "Waiting on Third Party",
}

PRIORITY_LABELS = {
    1: "Low",
    2: "Medium",
    3: "High",
    4: "Urgent",
}


def get_ticket(ticket_id: str) -> dict | None:
    resp = requests.get(
        f"{BASE_URL}/tickets/{ticket_id}",
        auth=AUTH,
        timeout=10,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def search_tickets_by_email(email: str) -> list:
    """Returns the most recent open ticket for the given email."""
    resp = requests.get(
        f"{BASE_URL}/tickets",
        auth=AUTH,
        params={"email": email, "order_by": "created_at", "order_type": "desc"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


agent = guava.Agent(
    name="Jordan",
    organization="Luminary Cloud",
    purpose=(
        "to help Luminary Cloud customers quickly check the status of their support tickets"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "fetch_ticket",
        objective=(
            "A customer is calling to check on a support ticket. Collect their ticket ID "
            "or email, look up the ticket, and give them a clear, helpful status update."
        ),
        checklist=[
            guava.Say(
                "Thanks for calling Luminary Cloud Support. I'm Jordan. "
                "I can pull up your ticket status — do you have your ticket number, "
                "or I can look it up by email?"
            ),
            guava.Field(
                key="lookup_method",
                field_type="multiple_choice",
                description="Ask how they'd like to look up their ticket.",
                choices=["by ticket number", "by email address"],
                required=True,
            ),
            guava.Field(
                key="ticket_id",
                field_type="text",
                description=(
                    "If looking up by ticket number, ask for it. Skip if using email."
                ),
                required=False,
            ),
            guava.Field(
                key="email",
                field_type="text",
                description=(
                    "If looking up by email, ask for their email address. Skip if using ticket number."
                ),
                required=False,
            ),
            guava.Field(
                key="caller_name",
                field_type="text",
                description="Ask for their name.",
                required=True,
            ),
        ],
    )


@agent.on_task_complete("fetch_ticket")
def on_done(call: guava.Call) -> None:
    method = call.get_field("lookup_method") or "by ticket number"
    ticket_id = (call.get_field("ticket_id") or "").strip()
    email = (call.get_field("email") or "").strip()
    name = call.get_field("caller_name") or "there"

    ticket = None

    try:
        if method == "by ticket number" and ticket_id:
            logging.info("Looking up Freshdesk ticket #%s for %s", ticket_id, name)
            ticket = get_ticket(ticket_id)
        elif email:
            logging.info("Looking up Freshdesk tickets for email %s", email)
            tickets = search_tickets_by_email(email)
            ticket = tickets[0] if tickets else None
    except Exception as e:
        logging.error("Freshdesk ticket lookup failed: %s", e)

    if not ticket:
        identifier = f"ticket #{ticket_id}" if ticket_id else f"email {email}"
        call.hangup(
            final_instructions=(
                f"Let {name} know you couldn't find a ticket for {identifier}. "
                "Suggest they double-check the ticket number or email and try again, "
                "or offer to open a new ticket for them. Be apologetic and helpful."
            )
        )
        return

    tid = ticket.get("id", "")
    subject = ticket.get("subject") or "your issue"
    status_code = ticket.get("status", 2)
    priority_code = ticket.get("priority", 2)
    updated = (ticket.get("updated_at") or "")[:10]

    status_label = STATUS_LABELS.get(status_code, "Unknown")
    priority_label = PRIORITY_LABELS.get(priority_code, "Unknown")

    logging.info(
        "Ticket #%s — status: %s, priority: %s, updated: %s",
        tid, status_label, priority_label, updated,
    )

    call.hangup(
        final_instructions=(
            f"Give {name} a clear status update. "
            f"Ticket #{tid}: '{subject}'. "
            f"Status: {status_label}. "
            f"Priority: {priority_label}. "
            f"Last updated: {updated}. "
            "If the status is 'Waiting on Customer', let them know we may need more information "
            "from them — check their email. If it's Resolved or Closed, inform them of that outcome. Thank them for calling Luminary Cloud."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])

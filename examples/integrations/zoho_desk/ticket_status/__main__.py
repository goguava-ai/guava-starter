import guava
import os
import logging
import requests

logging.basicConfig(level=logging.INFO)

ACCESS_TOKEN = os.environ["ZOHO_DESK_ACCESS_TOKEN"]
ORG_ID = os.environ["ZOHO_DESK_ORG_ID"]
HEADERS = {
    "Authorization": f"Zoho-oauthtoken {ACCESS_TOKEN}",
    "orgId": ORG_ID,
    "Content-Type": "application/json",
}
BASE_URL = "https://desk.zoho.com/api/v1"

STATUS_DESCRIPTIONS = {
    "Open": "open and being worked on by our support team",
    "On Hold": "on hold while we investigate further",
    "Escalated": "escalated to our senior support team",
    "Closed": "closed",
}

PRIORITY_DESCRIPTIONS = {
    "Low": "low",
    "Medium": "medium",
    "High": "high",
    "Urgent": "urgent",
}


def get_ticket(ticket_id: str) -> dict | None:
    """Fetches a single Zoho Desk ticket by ID. Returns the ticket object or None."""
    resp = requests.get(f"{BASE_URL}/tickets/{ticket_id}", headers=HEADERS, timeout=10)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def search_tickets_by_email(email: str, limit: int = 3) -> list[dict]:
    """Searches Zoho Desk for tickets associated with an email address."""
    resp = requests.get(
        f"{BASE_URL}/tickets",
        headers=HEADERS,
        params={"email": email, "limit": limit},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("data", [])


class TicketStatusController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Clearline Software",
            agent_name="Sam",
            agent_purpose="to help customers check the status of their support tickets",
        )

        self.set_task(
            objective=(
                "A customer has called to check on a support ticket. Collect how they'd like to "
                "look up their ticket — by ticket number or by email — then gather the identifier "
                "so we can look up their case."
            ),
            checklist=[
                guava.Say(
                    "Thank you for calling Clearline Software support. My name is Sam. "
                    "I can help you check the status of a support ticket."
                ),
                guava.Field(
                    key="lookup_method",
                    field_type="multiple_choice",
                    description=(
                        "Ask whether they'd like to look up their ticket by ticket number "
                        "or by the email address associated with their account."
                    ),
                    choices=["ticket-number", "email"],
                    required=True,
                ),
                guava.Field(
                    key="lookup_value",
                    field_type="text",
                    description=(
                        "Ask for the ticket number or email address depending on what they chose. "
                        "If ticket number, capture digits only. "
                        "If email, capture their full email address."
                    ),
                    required=True,
                ),
            ],
            on_complete=self.lookup_ticket,
        )

        self.accept_call()

    def lookup_ticket(self):
        lookup_method = self.get_field("lookup_method") or "email"
        lookup_value = (self.get_field("lookup_value") or "").strip()

        if lookup_method == "ticket-number":
            ticket_id = lookup_value.replace("#", "").strip()
            logging.info("Looking up ticket #%s", ticket_id)
            try:
                ticket = get_ticket(ticket_id)
            except Exception as e:
                logging.error("Failed to fetch ticket #%s: %s", ticket_id, e)
                ticket = None

            if ticket:
                self._read_ticket_status(ticket)
                return

            self.hangup(
                final_instructions=(
                    f"Let the caller know we could not find a ticket with number {ticket_id}. "
                    "Ask them to double-check the number from their confirmation email and call back. "
                    "Thank them for calling Clearline Software."
                )
            )

        else:
            # Lookup by email
            email = lookup_value
            logging.info("Searching for tickets by email: %s", email)
            try:
                tickets = search_tickets_by_email(email, limit=3)
            except Exception as e:
                logging.error("Failed to search tickets by email %s: %s", email, e)
                self.hangup(
                    final_instructions=(
                        "Apologize for a technical issue and let the caller know they can check "
                        "their ticket status by emailing support@clearlinesoft.com. "
                        "Thank them for their patience."
                    )
                )
                return

            if not tickets:
                self.hangup(
                    final_instructions=(
                        "Let the caller know we were unable to find any tickets associated with "
                        "that email address. Suggest they double-check the address or contact "
                        "support@clearlinesoft.com directly. Thank them for calling."
                    )
                )
                return

            # Surface the most recent ticket
            ticket = tickets[0]
            self._read_ticket_status(ticket, total_tickets=len(tickets))

    def _read_ticket_status(self, ticket: dict, total_tickets: int = 1):
        ticket_number = ticket.get("ticketNumber") or ticket.get("id")
        status = ticket.get("status", "Open")
        subject = ticket.get("subject", "your issue")
        priority = ticket.get("priority", "Medium")
        created_time = ticket.get("createdTime", "")
        modified_time = ticket.get("modifiedTime", "") or ticket.get("lastActivityTime", "")

        status_desc = STATUS_DESCRIPTIONS.get(status, status.lower())
        priority_desc = PRIORITY_DESCRIPTIONS.get(priority, priority.lower())

        logging.info(
            "Ticket #%s — status: %s, priority: %s, subject: %s",
            ticket_number, status, priority, subject,
        )

        multi_ticket_note = (
            f" You have {total_tickets} tickets on file — I'm reading back your most recent one."
            if total_tickets > 1
            else ""
        )

        created_note = f" It was created on {created_time[:10]}." if created_time else ""
        updated_note = f" Last updated on {modified_time[:10]}." if modified_time else ""

        if status in ("Open", "On Hold", "Escalated"):
            next_steps = "Our team will reach out by email once there is an update."
        elif status == "Closed":
            next_steps = "If the issue has recurred, please call back and we'll open a new ticket."
        else:
            next_steps = "Our team will be in touch if any action is needed."

        self.hangup(
            final_instructions=(
                f"Tell the caller:{multi_ticket_note} "
                f"Ticket #{ticket_number} regarding '{subject}' is currently {status_desc}. "
                f"Its priority is {priority_desc}.{created_note}{updated_note} "
                f"{next_steps} "
                "Thank them for calling Clearline Software."
            )
        )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=TicketStatusController,
    )

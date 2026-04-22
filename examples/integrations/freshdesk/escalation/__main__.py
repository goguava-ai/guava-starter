import guava
import os
import logging
from guava import logging_utils
import requests
from datetime import datetime, timezone


FRESHDESK_DOMAIN = os.environ["FRESHDESK_DOMAIN"]
FRESHDESK_API_KEY = os.environ["FRESHDESK_API_KEY"]

BASE_URL = f"https://{FRESHDESK_DOMAIN}.freshdesk.com/api/v2"
AUTH = (FRESHDESK_API_KEY, "X")

STATUS_LABELS = {2: "Open", 3: "Pending", 4: "Resolved", 5: "Closed"}


def get_ticket(ticket_id: str) -> dict | None:
    resp = requests.get(f"{BASE_URL}/tickets/{ticket_id}", auth=AUTH, timeout=10)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def escalate_ticket(ticket_id: str, escalation_note: str) -> None:
    """Bumps priority to Urgent, reopens if needed, and adds a private escalation note."""
    payload = {
        "priority": 4,   # Urgent
        "status": 2,     # Open
        "tags": ["escalated", "voice-escalation"],
    }
    requests.put(f"{BASE_URL}/tickets/{ticket_id}", auth=AUTH, json=payload, timeout=10).raise_for_status()

    note_payload = {"body": escalation_note, "private": True}
    requests.post(f"{BASE_URL}/tickets/{ticket_id}/notes", auth=AUTH, json=note_payload, timeout=10).raise_for_status()


class EscalationController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Luminary Cloud",
            agent_name="Jordan",
            agent_purpose=(
                "to help Luminary Cloud customers escalate an existing support ticket that "
                "hasn't been resolved to their satisfaction"
            ),
        )

        self.set_task(
            objective=(
                "A frustrated customer is calling to escalate an open support ticket. "
                "Empathize with them, collect their ticket number, understand why they're "
                "escalating, and formally escalate the ticket in Freshdesk."
            ),
            checklist=[
                guava.Say(
                    "Thank you for calling Luminary Cloud Support. I'm Jordan. "
                    "I understand you'd like to escalate an open support issue — "
                    "I'm sorry for the frustration and I'm here to help."
                ),
                guava.Field(
                    key="ticket_id",
                    field_type="text",
                    description="Ask for the ticket number they'd like to escalate.",
                    required=True,
                ),
                guava.Field(
                    key="caller_name",
                    field_type="text",
                    description="Ask for their name.",
                    required=True,
                ),
                guava.Field(
                    key="escalation_reason",
                    field_type="multiple_choice",
                    description="Ask why they're escalating.",
                    choices=[
                        "no response from the team",
                        "issue not resolved after multiple attempts",
                        "business impact is critical",
                        "promised SLA has been missed",
                        "other",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="escalation_detail",
                    field_type="text",
                    description=(
                        "Ask them to describe what's happened and what they expect. "
                        "Let them speak freely — capture the full detail."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="business_impact",
                    field_type="text",
                    description=(
                        "Ask if the unresolved issue is causing any specific business impact — "
                        "revenue loss, downtime, customer impact, etc."
                    ),
                    required=False,
                ),
            ],
            on_complete=self.process_escalation,
        )

        self.accept_call()

    def process_escalation(self):
        ticket_id = (self.get_field("ticket_id") or "").strip()
        name = self.get_field("caller_name") or "Unknown"
        reason = self.get_field("escalation_reason") or "other"
        detail = self.get_field("escalation_detail") or ""
        impact = self.get_field("business_impact") or ""

        logging.info("Processing escalation for ticket #%s — caller: %s, reason: %s", ticket_id, name, reason)

        try:
            ticket = get_ticket(ticket_id)
        except Exception as e:
            logging.error("Ticket lookup failed for #%s: %s", ticket_id, e)
            ticket = None

        if not ticket:
            self.hangup(
                final_instructions=(
                    f"Let {name} know you couldn't find a ticket with ID {ticket_id}. "
                    "Offer to create a new escalation ticket or transfer them to a manager. "
                    "Apologize for the inconvenience."
                )
            )
            return

        subject = ticket.get("subject") or "their issue"

        note_lines = [
            f"ESCALATION — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            f"Escalated by: {name} (via phone)",
            f"Reason: {reason}",
            f"Detail: {detail}",
        ]
        if impact:
            note_lines.append(f"Business impact: {impact}")

        try:
            escalate_ticket(ticket_id, "\n".join(note_lines))
            logging.info("Ticket #%s escalated to Urgent priority.", ticket_id)

            self.hangup(
                final_instructions=(
                    f"Let {name} know that ticket #{ticket_id} ('{subject}') has been formally "
                    "escalated to Urgent priority and flagged for senior attention. "
                    "Let them know a manager will personally review it and follow up within 2 hours. "
                    "Apologize for the experience and thank them for their patience."
                )
            )
        except Exception as e:
            logging.error("Failed to escalate ticket #%s: %s", ticket_id, e)
            self.hangup(
                final_instructions=(
                    f"Apologize to {name} for a technical issue. Let them know the escalation "
                    "has been manually noted and a manager will contact them within 2 hours. "
                    "Thank them for their patience."
                )
            )


if __name__ == "__main__":
    logging_utils.configure_logging()
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=EscalationController,
    )

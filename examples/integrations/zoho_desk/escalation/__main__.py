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

URGENCY_LABELS = {
    "system-down": "System Down",
    "data-loss": "Data Loss",
    "security-incident": "Security Incident",
    "revenue-impacting": "Revenue Impacting",
    "compliance-deadline": "Compliance Deadline",
}


def create_ticket(
    subject: str,
    description: str,
    contact_name: str,
    contact_email: str,
) -> dict:
    """Creates a new Zoho Desk ticket with Urgent priority and Escalated status."""
    payload = {
        "subject": subject,
        "description": description,
        "contact": {
            "email": contact_email,
            "lastName": contact_name,
        },
        "priority": "Urgent",
        "channel": "Voice",
        "status": "Escalated",
        "tags": [{"name": "guava"}, {"name": "voice"}, {"name": "escalated"}],
    }
    resp = requests.post(f"{BASE_URL}/tickets", headers=HEADERS, json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json()


def get_ticket(ticket_id: str) -> dict | None:
    """Fetches a single Zoho Desk ticket by ID. Returns the ticket object or None."""
    resp = requests.get(f"{BASE_URL}/tickets/{ticket_id}", headers=HEADERS, timeout=10)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def update_ticket_priority_and_status(ticket_id: str) -> dict:
    """Updates an existing ticket to Urgent priority and Escalated status."""
    payload = {
        "priority": "Urgent",
        "status": "Escalated",
    }
    resp = requests.patch(
        f"{BASE_URL}/tickets/{ticket_id}", headers=HEADERS, json=payload, timeout=10
    )
    resp.raise_for_status()
    return resp.json()


def add_internal_note(ticket_id: str, content: str) -> dict:
    """Posts a private internal note to a Zoho Desk ticket."""
    payload = {
        "content": content,
        "isPublic": False,
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
    name="Morgan",
    organization="Clearline Software",
    purpose=(
        "to triage urgent and critical support issues and escalate them immediately "
        "to the Clearline Software senior support team"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "escalate",
        objective=(
            "A customer has called with an urgent or critical issue. Collect their details, "
            "existing ticket ID if they have one, a summary of the issue, the business impact, "
            "and the reason for urgency. Then escalate immediately."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling Clearline Software support. My name is Morgan. "
                "I understand you have an urgent issue — I'm here to help get this "
                "escalated to the right team immediately."
            ),
            guava.Field(
                key="caller_name",
                field_type="text",
                description="Ask for their full name.",
                required=True,
            ),
            guava.Field(
                key="caller_email",
                field_type="text",
                description="Ask for their email address.",
                required=True,
            ),
            guava.Field(
                key="ticket_id",
                field_type="text",
                description=(
                    "Ask if they have an existing support ticket number related to this issue. "
                    "If they do, capture the ticket number. If not, capture 'none' — "
                    "we'll create a new ticket for them."
                ),
                required=False,
            ),
            guava.Field(
                key="issue_summary",
                field_type="text",
                description=(
                    "Ask them to describe the issue they're experiencing. "
                    "Capture their description clearly and in full."
                ),
                required=True,
            ),
            guava.Field(
                key="business_impact",
                field_type="text",
                description=(
                    "Ask how this issue is impacting their business right now — "
                    "for example, is it affecting all users, blocking revenue, "
                    "or causing data loss? Capture their full answer."
                ),
                required=True,
            ),
            guava.Field(
                key="urgency_reason",
                field_type="multiple_choice",
                description=(
                    "Ask what best describes the reason this is urgent. "
                    "Map their answer to one of the categories."
                ),
                choices=[
                    "system-down",
                    "data-loss",
                    "security-incident",
                    "revenue-impacting",
                    "compliance-deadline",
                ],
                required=True,
            ),
        ],
    )


@agent.on_task_complete("escalate")
def on_done(call: guava.Call) -> None:
    name = call.get_field("caller_name") or "Unknown Caller"
    email = call.get_field("caller_email") or ""
    ticket_id_raw = (call.get_field("ticket_id") or "").replace("#", "").strip()
    ticket_id = ticket_id_raw if ticket_id_raw.isdigit() else ""
    summary = call.get_field("issue_summary") or "Urgent issue reported by phone"
    business_impact = call.get_field("business_impact") or ""
    urgency_reason = call.get_field("urgency_reason") or "system-down"
    urgency_label = URGENCY_LABELS.get(urgency_reason, urgency_reason.replace("-", " ").title())

    internal_note = (
        f"ESCALATION — reported via inbound phone call\n\n"
        f"Caller: {name} ({email})\n"
        f"Urgency reason: {urgency_label}\n"
        f"Business impact: {business_impact}\n"
        f"Issue summary: {summary}"
    )

    if ticket_id:
        # Update existing ticket
        logging.info(
            "Escalating existing ticket #%s for %s (%s)", ticket_id, name, email
        )
        try:
            existing = get_ticket(ticket_id)
            if not existing:
                logging.warning(
                    "Ticket #%s not found — creating a new ticket instead", ticket_id
                )
                ticket_id = ""
            else:
                update_ticket_priority_and_status(ticket_id)
                add_internal_note(ticket_id, internal_note)
                ticket_number = existing.get("ticketNumber") or ticket_id
                logging.info("Ticket #%s escalated successfully", ticket_id)
                call.hangup(
                    final_instructions=(
                        f"Let {name} know their existing ticket #{ticket_number} has been "
                        f"escalated to our senior support team with urgent priority. "
                        f"The escalation reason on file is: {urgency_label}. "
                        "A senior engineer will review it immediately and reach out by email. "
                        "Thank them for calling Clearline Software and apologize for the disruption."
                    )
                )
                return
        except Exception as e:
            logging.error("Failed to escalate existing ticket #%s: %s", ticket_id, e)
            # Fall through to create a new ticket
            ticket_id = ""

    # Create a new ticket (either no ticket_id provided, or existing lookup failed)
    subject = f"[ESCALATED] {urgency_label} — {summary[:80]}"
    description = (
        f"{summary}\n\n"
        f"Business impact: {business_impact}\n"
        f"Urgency reason: {urgency_label}\n"
        f"Caller: {name} ({email})\n"
        "Source: Inbound phone call — escalation triage"
    )

    logging.info("Creating new escalated ticket for %s (%s)", name, email)
    try:
        ticket = create_ticket(
            subject=subject,
            description=description,
            contact_name=name,
            contact_email=email,
        )
        new_ticket_id = ticket.get("id") or ""
        ticket_number = ticket.get("ticketNumber") or new_ticket_id

        if new_ticket_id:
            try:
                add_internal_note(new_ticket_id, internal_note)
            except Exception as note_err:
                logging.error(
                    "Failed to add internal note to new ticket #%s: %s",
                    new_ticket_id, note_err,
                )

        logging.info("New escalated ticket created: #%s", ticket_number)
        call.hangup(
            final_instructions=(
                f"Let {name} know a new urgent escalation ticket has been created for them "
                f"as ticket #{ticket_number}. "
                f"The issue is logged as: {urgency_label}. "
                "Our senior support team will review it immediately and reach out by email. "
                "Thank them for calling Clearline Software and apologize for the disruption."
            )
        )
    except Exception as e:
        logging.error("Failed to create escalated ticket for %s: %s", name, e)
        call.hangup(
            final_instructions=(
                f"Apologize to {name} and let them know there was a technical issue "
                "creating the escalation ticket. Give them the direct escalation email: "
                "escalations@clearlinesoft.com and ask them to send their details there "
                "immediately. Thank them for their patience."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])

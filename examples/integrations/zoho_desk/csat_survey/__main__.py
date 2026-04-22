import guava
import os
import logging
from guava import logging_utils
import argparse
import requests
from datetime import datetime, timezone


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


def add_internal_note(ticket_id: str, content: str) -> dict:
    """Posts a private internal note to a Zoho Desk ticket (not visible to customer)."""
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


def close_ticket(ticket_id: str) -> dict:
    """Updates a Zoho Desk ticket status to Closed."""
    payload = {"status": "Closed"}
    resp = requests.patch(
        f"{BASE_URL}/tickets/{ticket_id}", headers=HEADERS, json=payload, timeout=10
    )
    resp.raise_for_status()
    return resp.json()


agent = guava.Agent(
    name="Taylor",
    organization="Clearline Software",
    purpose=(
        "to collect customer satisfaction feedback on behalf of Clearline Software "
        "after a support ticket has been resolved"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    ticket_id = call.get_variable("ticket_id")
    customer_name = call.get_variable("customer_name")

    # Pre-call: fetch the ticket to personalize the survey with the issue subject.
    ticket_subject = "your recent support request"
    try:
        ticket = get_ticket(ticket_id)
        if ticket and ticket.get("subject"):
            ticket_subject = f"'{ticket['subject']}'"
    except Exception as e:
        logging.error("Failed to fetch ticket #%s pre-call: %s", ticket_id, e)
    call.set_variable("ticket_subject", ticket_subject)

    call.reach_person(contact_full_name=customer_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    customer_name = call.get_variable("customer_name")
    ticket_id = call.get_variable("ticket_id")

    if outcome == "unavailable":
        logging.info(
            "Unable to reach %s for ticket #%s CSAT survey",
            customer_name, ticket_id,
        )
        call.hangup(
            final_instructions=(
                "Leave a brief, friendly voicemail on behalf of Clearline Software letting the "
                "customer know we were calling to follow up on their recently resolved support "
                "ticket. Let them know no action is needed and we hope everything is working well."
            )
        )
    elif outcome == "available":
        ticket_subject = call.get_variable("ticket_subject")
        call.set_task(
            "save_results",
            objective=(
                f"Collect CSAT feedback from {customer_name} regarding their recently "
                f"resolved ticket {ticket_subject}."
            ),
            checklist=[
                guava.Say(
                    f"Hi {customer_name}, this is Taylor calling from Clearline Software. "
                    f"I'm following up on your recently resolved support ticket regarding "
                    f"{ticket_subject}. I have just a couple of quick questions — "
                    "this will only take about a minute."
                ),
                guava.Field(
                    key="satisfaction_rating",
                    field_type="multiple_choice",
                    description=(
                        "Ask: 'On a scale of 1 to 5 — where 1 is very dissatisfied and 5 is very "
                        "satisfied — how would you rate the support you received?' "
                        "Capture their numeric rating."
                    ),
                    choices=["1", "2", "3", "4", "5"],
                    required=True,
                ),
                guava.Field(
                    key="resolution_quality",
                    field_type="multiple_choice",
                    description=(
                        "Ask: 'Was your issue fully resolved, partially resolved, or not resolved?' "
                        "Capture their answer."
                    ),
                    choices=["fully-resolved", "partially-resolved", "not-resolved"],
                    required=True,
                ),
                guava.Field(
                    key="open_feedback",
                    field_type="text",
                    description=(
                        "Ask: 'Is there anything we could have done better, or any other "
                        "feedback you'd like to share?' Capture their response, or skip "
                        "if they have nothing to add."
                    ),
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("save_results")
def on_done(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    ticket_id = call.get_variable("ticket_id")
    rating = call.get_field("satisfaction_rating") or "not provided"
    resolution = call.get_field("resolution_quality") or "not provided"
    feedback = call.get_field("open_feedback") or ""

    logging.info(
        "CSAT results for ticket #%s — rating: %s, resolution: %s",
        ticket_id, rating, resolution,
    )

    # Build internal note with survey results
    note_lines = [
        f"CSAT survey completed — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"Customer: {customer_name}",
        f"Satisfaction rating: {rating}/5",
        f"Resolution quality: {resolution.replace('-', ' ').title()}",
    ]
    if feedback and feedback.strip().lower() not in ("none", "n/a", ""):
        note_lines.append(f"Open feedback: {feedback}")

    try:
        add_internal_note(ticket_id, "\n".join(note_lines))
        logging.info("CSAT note added to ticket #%s", ticket_id)
    except Exception as e:
        logging.error("Failed to save CSAT note to ticket #%s: %s", ticket_id, e)

    # Close the ticket if the customer says it's fully resolved
    if resolution == "fully-resolved":
        try:
            close_ticket(ticket_id)
            logging.info("Ticket #%s closed after CSAT survey", ticket_id)
        except Exception as e:
            logging.error(
                "Failed to close ticket #%s after CSAT: %s", ticket_id, e
            )

    rating_int = int(rating) if rating.isdigit() else 0
    if rating_int <= 2:
        call.hangup(
            final_instructions=(
                f"Sincerely thank {customer_name} for their candid feedback. "
                "Acknowledge that we fell short of their expectations and let them know "
                "a member of our team will personally follow up to make things right. "
                "Apologize again and wish them a good day."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {customer_name} warmly for taking the time to share their feedback. "
                "Let them know their input helps us improve our support team. "
                "Wish them a great day and let them know we're here if they need anything else."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound CSAT survey call for a resolved Zoho Desk ticket."
    )
    parser.add_argument(
        "phone",
        help="Customer phone number to call (E.164 format, e.g. +15551234567)",
    )
    parser.add_argument("--ticket-id", required=True, help="Zoho Desk ticket ID")
    parser.add_argument("--name", required=True, help="Customer's full name")
    args = parser.parse_args()

    logging.info(
        "Initiating CSAT survey call to %s (%s) for ticket #%s",
        args.name, args.phone, args.ticket_id,
    )

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "ticket_id": args.ticket_id,
            "customer_name": args.name,
        },
    )

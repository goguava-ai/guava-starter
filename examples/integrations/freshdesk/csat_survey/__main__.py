import guava
import os
import logging
from guava import logging_utils
import argparse
import requests
from datetime import datetime, timezone


FRESHDESK_DOMAIN = os.environ["FRESHDESK_DOMAIN"]
FRESHDESK_API_KEY = os.environ["FRESHDESK_API_KEY"]

BASE_URL = f"https://{FRESHDESK_DOMAIN}.freshdesk.com/api/v2"
AUTH = (FRESHDESK_API_KEY, "X")


def get_ticket(ticket_id: str) -> dict | None:
    resp = requests.get(f"{BASE_URL}/tickets/{ticket_id}", auth=AUTH, timeout=10)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def add_private_note(ticket_id: str, body: str) -> None:
    """Adds a private agent note to the ticket with the CSAT survey results."""
    payload = {
        "body": body,
        "private": True,
    }
    resp = requests.post(
        f"{BASE_URL}/tickets/{ticket_id}/notes",
        auth=AUTH,
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()


def update_ticket_custom_fields(ticket_id: str, rating: int, resolved: str) -> None:
    """Updates custom CSAT fields on the ticket."""
    payload = {
        "custom_fields": {
            "cf_csat_score": rating,
            "cf_csat_resolved": resolved,
            "cf_csat_channel": "voice",
        }
    }
    resp = requests.put(
        f"{BASE_URL}/tickets/{ticket_id}",
        auth=AUTH,
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()


agent = guava.Agent(
    name="Taylor",
    organization="Luminary Cloud",
    purpose=(
        "to collect customer satisfaction feedback after a Freshdesk support ticket "
        "has been resolved"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    ticket_id = call.get_variable("ticket_id")
    customer_name = call.get_variable("customer_name")

    ticket_subject = "your recent support request"
    try:
        ticket = get_ticket(ticket_id)
        if ticket and ticket.get("subject"):
            ticket_subject = f"'{ticket['subject']}'"
    except Exception as e:
        logging.error("Failed to fetch ticket #%s pre-call: %s", ticket_id, e)

    call.ticket_subject = ticket_subject

    call.set_task(
        "collect_csat",
        objective=(
            f"Collect CSAT feedback from {customer_name} about their recently "
            f"resolved ticket {ticket_subject}. Keep it brief — aim for under two minutes."
        ),
        checklist=[
            guava.Say(
                f"Hi {customer_name}, this is Taylor from Luminary Cloud Support. "
                f"I'm following up on your recently resolved ticket regarding "
                f"{ticket_subject}. I have two quick questions — it'll only take a minute."
            ),
            guava.Field(
                key="satisfaction",
                field_type="multiple_choice",
                description=(
                    "Ask: 'On a scale of 1 to 5, how satisfied were you with the support you received?' "
                    "1 is very dissatisfied, 5 is very satisfied."
                ),
                choices=["1", "2", "3", "4", "5"],
                required=True,
            ),
            guava.Field(
                key="resolved",
                field_type="multiple_choice",
                description="Ask: 'Was your issue fully resolved?'",
                choices=["yes", "partially", "no"],
                required=True,
            ),
            guava.Field(
                key="feedback",
                field_type="text",
                description=(
                    "Ask: 'Is there anything we could have done better?' "
                    "Keep it optional — accept 'nothing' or silence."
                ),
                required=False,
            ),
        ],
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    if outcome == "unavailable":
        customer_name = call.get_variable("customer_name")
        ticket_id = call.get_variable("ticket_id")
        logging.info("Unable to reach %s for CSAT survey on ticket #%s.", customer_name, ticket_id)
        call.hangup(
            final_instructions=(
                f"Leave a brief, friendly voicemail for {customer_name} from Luminary Cloud Support. "
                "Let them know you were calling to follow up on their resolved support ticket "
                "and that no action is needed. Wish them a good day."
            )
        )
    elif outcome == "available":
        ticket_id = call.get_variable("ticket_id")
        customer_name = call.get_variable("customer_name")

        ticket_subject = "your recent support request"
        try:
            ticket = get_ticket(ticket_id)
            if ticket and ticket.get("subject"):
                ticket_subject = f"'{ticket['subject']}'"
        except Exception as e:
            logging.error("Failed to fetch ticket #%s pre-call: %s", ticket_id, e)

        call.ticket_subject = ticket_subject

        call.set_task(
            "collect_csat",
            objective=(
                f"Collect CSAT feedback from {customer_name} about their recently "
                f"resolved ticket {ticket_subject}. Keep it brief — aim for under two minutes."
            ),
            checklist=[
                guava.Say(
                    f"Hi {customer_name}, this is Taylor from Luminary Cloud Support. "
                    f"I'm following up on your recently resolved ticket regarding "
                    f"{ticket_subject}. I have two quick questions — it'll only take a minute."
                ),
                guava.Field(
                    key="satisfaction",
                    field_type="multiple_choice",
                    description=(
                        "Ask: 'On a scale of 1 to 5, how satisfied were you with the support you received?' "
                        "1 is very dissatisfied, 5 is very satisfied."
                    ),
                    choices=["1", "2", "3", "4", "5"],
                    required=True,
                ),
                guava.Field(
                    key="resolved",
                    field_type="multiple_choice",
                    description="Ask: 'Was your issue fully resolved?'",
                    choices=["yes", "partially", "no"],
                    required=True,
                ),
                guava.Field(
                    key="feedback",
                    field_type="text",
                    description=(
                        "Ask: 'Is there anything we could have done better?' "
                        "Keep it optional — accept 'nothing' or silence."
                    ),
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("collect_csat")
def on_done(call: guava.Call) -> None:
    ticket_id = call.get_variable("ticket_id")
    customer_name = call.get_variable("customer_name")

    satisfaction = call.get_field("satisfaction") or "0"
    resolved = call.get_field("resolved") or "yes"
    feedback = call.get_field("feedback") or ""

    try:
        rating = int(satisfaction)
    except ValueError:
        rating = 0

    logging.info(
        "CSAT for ticket #%s — rating: %s/5, resolved: %s",
        ticket_id, satisfaction, resolved,
    )

    note_lines = [
        f"CSAT survey — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"Customer: {customer_name}",
        f"Satisfaction: {satisfaction}/5",
        f"Issue fully resolved: {resolved}",
    ]
    if feedback and feedback.lower().strip() not in ("nothing", "none", "n/a", ""):
        note_lines.append(f"Feedback: {feedback}")

    try:
        add_private_note(ticket_id, "\n".join(note_lines))
        logging.info("CSAT note added to ticket #%s", ticket_id)
    except Exception as e:
        logging.error("Failed to add note to ticket #%s: %s", ticket_id, e)

    try:
        update_ticket_custom_fields(ticket_id, rating, resolved)
        logging.info("CSAT custom fields updated on ticket #%s.", ticket_id)
    except Exception as e:
        logging.warning("Could not update CSAT custom fields (may not be configured): %s", e)

    if rating <= 2 or resolved == "no":
        call.hangup(
            final_instructions=(
                f"Sincerely thank {customer_name} for their honest feedback. "
                "Acknowledge that we fell short and let them know a support manager will "
                "personally follow up to make it right. Be empathetic and non-defensive."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {customer_name} warmly for their time and positive feedback. "
                "Let them know Luminary Cloud is always here if they need anything. "
                "Wish them a great day."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound CSAT survey for a resolved Freshdesk ticket."
    )
    parser.add_argument("phone", help="Customer's phone number (E.164, e.g. +15551234567)")
    parser.add_argument("--ticket-id", required=True, help="Freshdesk ticket ID")
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

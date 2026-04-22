import guava
import os
import logging
import base64
import argparse
import requests
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)

ZENDESK_SUBDOMAIN = os.environ["ZENDESK_SUBDOMAIN"]
ZENDESK_EMAIL = os.environ["ZENDESK_EMAIL"]
ZENDESK_API_TOKEN = os.environ["ZENDESK_API_TOKEN"]

_encoded = base64.b64encode(f"{ZENDESK_EMAIL}/token:{ZENDESK_API_TOKEN}".encode()).decode()
HEADERS = {
    "Authorization": f"Basic {_encoded}",
    "Content-Type": "application/json",
}
BASE_URL = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com/api/v2"


def get_ticket_with_comments(ticket_id: str) -> tuple[dict | None, list[dict]]:
    """
    Fetches a ticket and its public comments in one sideloaded request.
    Returns (ticket, comments) or (None, []) if not found.
    """
    resp = requests.get(
        f"{BASE_URL}/tickets/{ticket_id}",
        headers=HEADERS,
        params={"include": "comment_count"},
        timeout=10,
    )
    if resp.status_code == 404:
        return None, []
    resp.raise_for_status()
    ticket = resp.json()["ticket"]

    # Fetch the most recent public comment to relay to the customer.
    comments_resp = requests.get(
        f"{BASE_URL}/tickets/{ticket_id}/comments",
        headers=HEADERS,
        params={"sort_order": "desc", "per_page": "5"},
        timeout=10,
    )
    comments_resp.raise_for_status()
    all_comments = comments_resp.json().get("comments", [])
    # Only surface public comments (not internal agent notes)
    public_comments = [c for c in all_comments if c.get("public", True)]

    return ticket, public_comments


def add_call_log_note(ticket_id: str, customer_name: str, outcome: str) -> None:
    """Records an internal note that the customer was called and what happened."""
    note = (
        f"Proactive update call — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n"
        f"Customer: {customer_name}\n"
        f"Outcome: {outcome}"
    )
    payload = {
        "ticket": {
            "comment": {
                "body": note,
                "public": False,
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


class ProactiveUpdateController(guava.CallController):
    def __init__(self, ticket_id: str, customer_name: str, update_summary: str):
        super().__init__()
        self.ticket_id = ticket_id
        self.customer_name = customer_name
        self.update_summary = update_summary
        self.ticket_subject = "your support request"
        self.ticket_status = "open"
        self.latest_agent_comment = ""

        # Pre-call: fetch the ticket and its most recent public comment.
        # This gives the agent enough context to relay a specific update rather than
        # a generic "we're working on it" message.
        try:
            ticket, public_comments = get_ticket_with_comments(ticket_id)
            if ticket:
                self.ticket_status = ticket.get("status", "open")
                if ticket.get("subject"):
                    self.ticket_subject = f"'{ticket['subject']}'"

            # Find the most recent comment not authored by the requester (i.e., from an agent).
            requester_id = ticket.get("requester_id") if ticket else None
            for comment in public_comments:
                if comment.get("author_id") != requester_id:
                    self.latest_agent_comment = comment.get("body", "")
                    break
        except Exception as e:
            logging.error("Failed to fetch ticket #%s pre-call: %s", ticket_id, e)

        self.set_persona(
            organization_name="Horizon Software",
            agent_name="Morgan",
            agent_purpose=(
                "to proactively notify customers of important updates on their support tickets "
                "on behalf of Horizon Software"
            ),
        )

        self.reach_person(
            contact_full_name=self.customer_name,
            on_success=self.deliver_update,
            on_failure=self.recipient_unavailable,
        )

    def deliver_update(self):
        status = self.ticket_status
        is_resolved = status in ("solved", "closed")

        self.set_task(
            objective=(
                f"Deliver a support ticket update to {self.customer_name} regarding "
                f"{self.ticket_subject} and confirm they received the information."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.customer_name}, this is Morgan calling from Horizon Software. "
                    f"I'm calling with an update on your support ticket regarding "
                    f"{self.ticket_subject}."
                ),
                guava.Say(self.update_summary),
                guava.Field(
                    key="update_acknowledged",
                    field_type="text",
                    description=(
                        "Confirm the customer heard and understands the update. "
                        "Capture 'yes' when they acknowledge."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="has_questions",
                    field_type="multiple_choice",
                    description=(
                        "Ask if they have any questions about the update or if there is "
                        "anything else we can help them with."
                    ),
                    choices=["yes", "no"],
                    required=True,
                ),
                guava.Field(
                    key="question_detail",
                    field_type="text",
                    description=(
                        "If they have questions, ask them to share their question or concern. "
                        "Capture their full question. Skip if they said no."
                    ),
                    required=False,
                ),
            ],
            on_complete=lambda: self.wrap_up(is_resolved),
        )

    def wrap_up(self, is_resolved: bool):
        has_questions = self.get_field("has_questions") or "no"
        question_detail = self.get_field("question_detail") or ""

        outcome_parts = ["Customer reached and update delivered."]
        if has_questions == "yes" and question_detail:
            outcome_parts.append(f"Customer question: {question_detail}")
        outcome_parts.append(f"Ticket status at time of call: {self.ticket_status}.")

        outcome = " ".join(outcome_parts)
        logging.info("Proactive update call complete for ticket #%s — %s", self.ticket_id, outcome)

        try:
            add_call_log_note(self.ticket_id, self.customer_name, outcome)
            logging.info("Call log note added to ticket #%s", self.ticket_id)
        except Exception as e:
            logging.error("Failed to add call log note to ticket #%s: %s", self.ticket_id, e)

        if has_questions == "yes":
            self.hangup(
                final_instructions=(
                    f"Let {self.customer_name} know that their question has been noted on the ticket "
                    "and a support engineer will follow up by email with an answer. "
                    + (
                        "Since the ticket is resolved, let them know we can reopen it to address "
                        "their question. "
                        if is_resolved
                        else ""
                    )
                    + "Thank them for their patience and for being a Horizon Software customer."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    f"Thank {self.customer_name} for their time. "
                    + (
                        "Let them know the ticket is resolved and they can reach out anytime "
                        "if the issue recurs. "
                        if is_resolved
                        else "Let them know we'll continue to keep them updated. "
                    )
                    + "Wish them a great day."
                )
            )

    def recipient_unavailable(self):
        logging.info(
            "Unable to reach %s for proactive update on ticket #%s",
            self.customer_name, self.ticket_id,
        )
        try:
            add_call_log_note(
                self.ticket_id,
                self.customer_name,
                "Proactive update call attempted — customer not available, voicemail left.",
            )
        except Exception as e:
            logging.error("Failed to add call log note: %s", e)

        self.hangup(
            final_instructions=(
                f"Leave a brief voicemail for {self.customer_name} on behalf of Horizon Software. "
                f"Let them know you're calling with an update on {self.ticket_subject} and ask "
                "them to check their email for full details. Provide a callback number and "
                "let them know our team is available Monday through Friday, 9am to 6pm Eastern."
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Outbound proactive ticket update call for a Zendesk ticket."
    )
    parser.add_argument("phone", help="Customer phone number to call (E.164 format, e.g. +15551234567)")
    parser.add_argument("--ticket-id", required=True, help="Zendesk ticket ID")
    parser.add_argument("--name", required=True, help="Customer's full name")
    parser.add_argument(
        "--update",
        required=True,
        help="The update message to deliver (spoken verbatim by the agent)",
    )
    args = parser.parse_args()

    logging.info(
        "Initiating proactive update call to %s (%s) for ticket #%s",
        args.name, args.phone, args.ticket_id,
    )

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=ProactiveUpdateController(
            ticket_id=args.ticket_id,
            customer_name=args.name,
            update_summary=args.update,
        ),
    )

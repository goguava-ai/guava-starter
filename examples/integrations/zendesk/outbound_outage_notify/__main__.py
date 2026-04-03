import guava
import os
import logging
import base64
import argparse
import requests
from datetime import datetime

logging.basicConfig(level=logging.INFO)

ZENDESK_SUBDOMAIN = os.environ["ZENDESK_SUBDOMAIN"]
ZENDESK_EMAIL = os.environ["ZENDESK_EMAIL"]
ZENDESK_API_TOKEN = os.environ["ZENDESK_API_TOKEN"]

# The problem ticket ID for the ongoing outage. All related incident tickets
# will be linked to this ticket via the problem/incident relationship.
PROBLEM_TICKET_ID = int(os.environ["ZENDESK_PROBLEM_TICKET_ID"])

_encoded = base64.b64encode(f"{ZENDESK_EMAIL}/token:{ZENDESK_API_TOKEN}".encode()).decode()
HEADERS = {
    "Authorization": f"Basic {_encoded}",
    "Content-Type": "application/json",
}
BASE_URL = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com/api/v2"


def get_incident_tickets(problem_ticket_id: int) -> list[dict]:
    """
    Returns all open incident tickets linked to a problem ticket.
    Uses the /tickets/{id}/incidents endpoint.
    """
    resp = requests.get(
        f"{BASE_URL}/tickets/{problem_ticket_id}/incidents",
        headers=HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    return [
        t for t in resp.json().get("tickets", [])
        if t.get("status") not in ("solved", "closed")
    ]


def get_user(user_id: int) -> dict | None:
    """Fetches a Zendesk user by ID."""
    resp = requests.get(f"{BASE_URL}/users/{user_id}", headers=HEADERS, timeout=10)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()["user"]


def add_public_comment(ticket_id: int, body: str) -> None:
    """Posts a public comment to a ticket — visible to the requester."""
    payload = {
        "ticket": {
            "comment": {"body": body, "public": True},
        }
    }
    resp = requests.put(
        f"{BASE_URL}/tickets/{ticket_id}",
        headers=HEADERS,
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()


class OutageNotifyController(guava.CallController):
    def __init__(self, customer_name: str, ticket_id: int, outage_message: str):
        super().__init__()
        self.customer_name = customer_name
        self.ticket_id = ticket_id
        self.outage_message = outage_message

        self.set_persona(
            organization_name="Horizon Software",
            agent_name="Morgan",
            agent_purpose=(
                "to notify customers affected by an active service outage and provide "
                "a status update on behalf of Horizon Software"
            ),
        )

        self.reach_person(
            contact_full_name=self.customer_name,
            on_success=self.deliver_notification,
            on_failure=self.recipient_unavailable,
        )

    def deliver_notification(self):
        self.set_task(
            objective=(
                f"Notify {self.customer_name} about the current service outage and confirm "
                "they received the update."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.customer_name}, this is Morgan calling from Horizon Software. "
                    "I'm calling because we've identified a service issue that may be affecting your account "
                    "and I wanted to give you a direct update."
                ),
                guava.Say(self.outage_message),
                guava.Field(
                    key="acknowledged",
                    field_type="text",
                    description=(
                        "Confirm the customer heard and acknowledges the update. "
                        "Capture 'yes' when they confirm."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="needs_callback",
                    field_type="multiple_choice",
                    description=(
                        "Ask if they would like a callback from a support engineer once "
                        "the issue is fully resolved."
                    ),
                    choices=["yes", "no"],
                    required=True,
                ),
            ],
            on_complete=self.log_outcome,
        )

    def log_outcome(self):
        needs_callback = self.get_field("needs_callback") or "no"

        comment_body = (
            f"Outage notification call completed — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n"
            f"Customer notified: {self.customer_name}\n"
            f"Callback requested: {needs_callback}"
        )

        try:
            add_public_comment(self.ticket_id, comment_body)
            logging.info("Notification logged on ticket #%s", self.ticket_id)
        except Exception as e:
            logging.error("Failed to log notification on ticket #%s: %s", self.ticket_id, e)

        if needs_callback == "yes":
            self.hangup(
                final_instructions=(
                    f"Let {self.customer_name} know a support engineer will call them back "
                    "as soon as the service is restored. Apologize again for the disruption "
                    "and thank them for their patience with Horizon Software."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    f"Thank {self.customer_name} for their time and understanding. "
                    "Let them know we'll send an email notification when service is fully restored. "
                    "Apologize for the inconvenience and wish them a good day."
                )
            )

    def recipient_unavailable(self):
        logging.info("Unable to reach %s for outage notification", self.customer_name)
        try:
            add_public_comment(
                self.ticket_id,
                (
                    f"Outage notification attempted — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n"
                    f"Customer: {self.customer_name} — not available, voicemail left."
                ),
            )
        except Exception as e:
            logging.error("Failed to log voicemail attempt on ticket #%s: %s", self.ticket_id, e)

        self.hangup(
            final_instructions=(
                f"Leave a concise voicemail for {self.customer_name} on behalf of Horizon Software. "
                "Let them know we're calling about a known service issue affecting their account, "
                "that our team is actively working on a fix, and they'll receive an email update "
                "as soon as service is restored. Provide our support line number for questions."
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Outbound outage notification campaign. Fetches all open incident tickets linked "
            "to a problem ticket and calls each requester."
        )
    )
    parser.add_argument(
        "--outage-message",
        required=True,
        help="The outage status message to deliver verbatim on each call.",
    )
    args = parser.parse_args()

    logging.info(
        "Fetching open incident tickets linked to problem ticket #%s", PROBLEM_TICKET_ID
    )
    try:
        incident_tickets = get_incident_tickets(PROBLEM_TICKET_ID)
    except Exception as e:
        logging.error("Failed to fetch incident tickets: %s", e)
        raise SystemExit(1)

    logging.info("Found %d open incident tickets to notify", len(incident_tickets))

    agent_number = os.environ["GUAVA_AGENT_NUMBER"]
    client = guava.Client()

    for ticket in incident_tickets:
        ticket_id = ticket["id"]
        requester_id = ticket.get("requester_id")

        if not requester_id:
            logging.warning("Ticket #%s has no requester — skipping", ticket_id)
            continue

        try:
            user = get_user(requester_id)
        except Exception as e:
            logging.error("Failed to fetch user %s for ticket #%s: %s", requester_id, ticket_id, e)
            continue

        if not user or not user.get("phone"):
            logging.warning(
                "Ticket #%s requester %s has no phone number — skipping",
                ticket_id, requester_id,
            )
            continue

        customer_name = user["name"]
        phone = user["phone"]

        logging.info(
            "Calling %s (%s) for ticket #%s", customer_name, phone, ticket_id
        )
        try:
            client.create_outbound(
                from_number=agent_number,
                to_number=phone,
                call_controller=OutageNotifyController(
                    customer_name=customer_name,
                    ticket_id=ticket_id,
                    outage_message=args.outage_message,
                ),
            )
        except Exception as e:
            logging.error(
                "Failed to initiate call to %s for ticket #%s: %s", phone, ticket_id, e
            )

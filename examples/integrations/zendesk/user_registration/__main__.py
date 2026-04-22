import guava
import os
import logging
from guava import logging_utils
import base64
import requests


ZENDESK_SUBDOMAIN = os.environ["ZENDESK_SUBDOMAIN"]
ZENDESK_EMAIL = os.environ["ZENDESK_EMAIL"]
ZENDESK_API_TOKEN = os.environ["ZENDESK_API_TOKEN"]

_encoded = base64.b64encode(f"{ZENDESK_EMAIL}/token:{ZENDESK_API_TOKEN}".encode()).decode()
HEADERS = {
    "Authorization": f"Basic {_encoded}",
    "Content-Type": "application/json",
}
BASE_URL = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com/api/v2"


def find_user_by_email(email: str) -> dict | None:
    """Searches Zendesk for an existing end-user by email."""
    resp = requests.get(
        f"{BASE_URL}/users/search",
        headers=HEADERS,
        params={"query": email},
        timeout=10,
    )
    resp.raise_for_status()
    results = resp.json().get("results", [])
    # Filter to end-users only (exclude agents/admins)
    end_users = [u for u in results if u.get("role") == "end-user"]
    return end_users[0] if end_users else None


def create_user(name: str, email: str, phone: str, organization_name: str) -> dict:
    """
    Creates a new Zendesk end-user.
    If organization_name is provided, Zendesk will look up or create the org automatically.
    """
    user: dict[str, object] = {
        "name": name,
        "email": email,
        "role": "end-user",
        "verified": True,
    }
    payload: dict[str, object] = {"user": user}
    if phone:
        user["phone"] = phone
    if organization_name:
        user["organization"] = {"name": organization_name}

    resp = requests.post(f"{BASE_URL}/users", headers=HEADERS, json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json()["user"]


def create_ticket_for_user(user_id: int, subject: str, body: str) -> dict:
    """Creates a ticket linked to an existing Zendesk user by their ID."""
    payload = {
        "ticket": {
            "subject": subject,
            "comment": {"body": body},
            "requester_id": user_id,
            "priority": "normal",
            "tags": ["new-customer", "voice", "guava"],
        }
    }
    resp = requests.post(f"{BASE_URL}/tickets", headers=HEADERS, json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json()["ticket"]


agent = guava.Agent(
    name="Jordan",
    organization="Horizon Software",
    purpose=(
        "to register new customers in Horizon Software's support system "
        "and open their first support ticket"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "register_and_open_ticket",
        objective=(
            "A new customer has called Horizon Software support. Check if they already have "
            "an account, register them if not, and open their first support ticket."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling Horizon Software support. My name is Jordan. "
                "I'd be happy to get you set up in our system today."
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
                description=(
                    "Ask for their email address. This will be their support account login "
                    "and where ticket updates will be sent."
                ),
                required=True,
            ),
            guava.Field(
                key="caller_phone",
                field_type="text",
                description=(
                    "Ask for their phone number in case we need to call them back. "
                    "Optional — capture 'none' if they prefer not to share."
                ),
                required=False,
            ),
            guava.Field(
                key="company_name",
                field_type="text",
                description=(
                    "Ask for the name of their company or organization. "
                    "Capture 'individual' if they are not representing a company."
                ),
                required=False,
            ),
            guava.Field(
                key="issue_summary",
                field_type="text",
                description=(
                    "Ask what brought them to support today — what issue or question "
                    "they'd like help with. Capture a clear summary."
                ),
                required=True,
            ),
        ],
    )


@agent.on_task_complete("register_and_open_ticket")
def on_done(call: guava.Call) -> None:
    name = call.get_field("caller_name") or "Unknown Caller"
    email = call.get_field("caller_email") or ""
    phone_raw = call.get_field("caller_phone") or ""
    phone = "" if phone_raw.strip().lower() in ("none", "n/a", "") else phone_raw.strip()
    company = call.get_field("company_name") or ""
    if company.strip().lower() == "individual":
        company = ""
    issue = call.get_field("issue_summary") or "General support request"

    # Step 1: Check if a Zendesk end-user already exists for this email.
    existing_user = None
    try:
        existing_user = find_user_by_email(email)
    except Exception as e:
        logging.error("Failed to search for existing user: %s", e)

    if existing_user:
        zendesk_user = existing_user
        logging.info(
            "Existing Zendesk user found: #%s (%s)", existing_user["id"], email
        )
    else:
        # Step 2: Create a new end-user in Zendesk.
        logging.info("Creating new Zendesk user for %s (%s)", name, email)
        try:
            zendesk_user = create_user(
                name=name,
                email=email,
                phone=phone,
                organization_name=company,
            )
            logging.info("New Zendesk user created: #%s", zendesk_user["id"])
        except Exception as e:
            logging.error("Failed to create Zendesk user: %s", e)
            call.hangup(
                final_instructions=(
                    f"Apologize to {name} for a technical issue registering their account. "
                    "Ask them to email support@horizonsoftware.com with their name, email, "
                    "and issue description so a team member can assist. Thank them."
                )
            )
            return

    # Step 3: Open their first (or next) support ticket linked to the user record.
    user_id = zendesk_user["id"]
    is_new = not existing_user

    logging.info("Creating ticket for user #%s — issue: %s", user_id, issue)
    try:
        ticket = create_ticket_for_user(
            user_id=user_id,
            subject=issue,
            body=f"{issue}\n\nSource: Inbound phone call",
        )
        ticket_id = ticket["id"]
        logging.info("Ticket #%s created for user #%s", ticket_id, user_id)

        call.hangup(
            final_instructions=(
                (
                    f"Let {name} know their new support account has been created "
                    "and they'll receive a welcome email shortly. "
                    if is_new
                    else f"Let {name} know we found their existing account. "
                )
                + f"Their support ticket has been opened as ticket #{ticket_id}. "
                "Our team will be in touch by email soon. "
                "Thank them for choosing Horizon Software."
            )
        )
    except Exception as e:
        logging.error("Failed to create ticket for user #%s: %s", user_id, e)
        call.hangup(
            final_instructions=(
                f"Let {name} know their account is set up but we had trouble opening the ticket. "
                "Ask them to email support@horizonsoftware.com with their issue. Thank them."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])

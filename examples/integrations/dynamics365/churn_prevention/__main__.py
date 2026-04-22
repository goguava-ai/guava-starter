import guava
import os
import logging
from guava import logging_utils
import argparse
import requests
from datetime import datetime, timezone


ACCESS_TOKEN = os.environ["DYNAMICS_ACCESS_TOKEN"]
ORG_URL = os.environ["DYNAMICS_ORG_URL"]  # e.g. https://yourorg.crm.dynamics.com

_BASE_HEADERS = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json",
    "OData-MaxVersion": "4.0",
    "OData-Version": "4.0",
    "Accept": "application/json",
}
HEADERS = {**_BASE_HEADERS, "Prefer": "return=representation"}  # for POST/PATCH that return data
GET_HEADERS = _BASE_HEADERS  # for GET requests

API_BASE = f"{ORG_URL}/api/data/v9.2"


def get_contact(contact_id: str) -> dict | None:
    """Fetches a contact record by ID. Returns the contact or None."""
    resp = requests.get(
        f"{API_BASE}/contacts({contact_id})",
        headers=GET_HEADERS,
        params={
            "$select": "fullname,emailaddress1,telephone1,accountid",
        },
        timeout=10,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def add_contact_note(contact_id: str, subject: str, note_text: str) -> None:
    """Posts an internal note (annotation) linked directly to a contact record."""
    payload = {
        "subject": subject,
        "notetext": note_text,
        "objectid_contact@odata.bind": f"/contacts({contact_id})",
        "objecttypecode": "contact",
    }
    resp = requests.post(f"{API_BASE}/annotations", headers=HEADERS, json=payload, timeout=10)
    resp.raise_for_status()


def log_phone_call(contact_id: str, subject: str, description: str) -> None:
    """Logs a completed outbound phone call activity against a contact."""
    payload = {
        "subject": subject,
        "description": description,
        "directioncode": True,  # outbound
        "regardingobjectid_contact@odata.bind": f"/contacts({contact_id})",
    }
    resp = requests.post(f"{API_BASE}/phonecalls", headers=HEADERS, json=payload, timeout=10)
    resp.raise_for_status()


agent = guava.Agent(
    name="Taylor",
    organization="Pinnacle Solutions",
    purpose=(
        "to proactively reach out to at-risk customers on behalf of Pinnacle Solutions, "
        "understand their concerns, and help identify the right next steps to retain them"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    contact_id = call.get_variable("contact_id")

    # Fetch contact details for context
    contact_email = ""
    try:
        contact = get_contact(contact_id)
        if contact:
            contact_email = contact.get("emailaddress1", "")
    except Exception as e:
        logging.error("Failed to fetch contact %s pre-call: %s", contact_id, e)

    call.set_variable("contact_email", contact_email)
    call.reach_person(contact_full_name=contact_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    contact_name = call.get_variable("contact_name")
    contact_id = call.get_variable("contact_id")
    if outcome == "unavailable":
        logging.info(
            "Unable to reach %s (contact %s) for churn prevention call",
            contact_name, contact_id,
        )
        call.hangup(
            final_instructions=(
                f"Leave a brief, professional voicemail for {contact_name} on behalf of "
                "Pinnacle Solutions. Let them know you were calling to check in and see how "
                "things are going. Invite them to call back at their convenience or reply to "
                "any recent email from our team. Wish them a great day."
            )
        )
    elif outcome == "available":
        call.set_task(
            "save_results",
            objective=(
                f"Connect with {contact_name} to understand their satisfaction with "
                "Pinnacle Solutions, surface any concerns, and determine the best next step "
                "to support their continued success."
            ),
            checklist=[
                guava.Say(
                    f"Hi {contact_name}, this is Taylor calling from Pinnacle Solutions. "
                    "I'm reaching out because we value your partnership and wanted to check in "
                    "to make sure everything is going well for you. Do you have a few minutes?"
                ),
                guava.Field(
                    key="satisfaction",
                    field_type="multiple_choice",
                    description=(
                        "Ask: 'Overall, how would you describe your satisfaction with "
                        "Pinnacle Solutions?' Map their answer to the closest level."
                    ),
                    choices=[
                        "very-satisfied",
                        "satisfied",
                        "neutral",
                        "dissatisfied",
                        "very-dissatisfied",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="primary_concern",
                    field_type="text",
                    description=(
                        "If they expressed any dissatisfaction or neutral sentiment, ask: "
                        "'Could you tell me a bit more about what has been on your mind?' "
                        "Capture their main concern. Skip if they are fully satisfied."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="likelihood_to_renew",
                    field_type="multiple_choice",
                    description=(
                        "Ask: 'When it comes to renewing your relationship with Pinnacle Solutions, "
                        "how would you describe your current thinking?'"
                    ),
                    choices=[
                        "very-likely",
                        "likely",
                        "unsure",
                        "unlikely",
                        "not-renewing",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="requested_next_step",
                    field_type="multiple_choice",
                    description=(
                        "Ask: 'What would be most helpful for you right now?' "
                        "Offer the options and let them choose."
                    ),
                    choices=[
                        "speak-with-account-manager",
                        "technical-support",
                        "pricing-review",
                        "no-action-needed",
                    ],
                    required=True,
                ),
            ],
        )


@agent.on_task_complete("save_results")
def on_save_results(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    contact_id = call.get_variable("contact_id")
    satisfaction = call.get_field("satisfaction") or "not provided"
    primary_concern = call.get_field("primary_concern") or ""
    likelihood = call.get_field("likelihood_to_renew") or "not provided"
    next_step = call.get_field("requested_next_step") or "no-action-needed"

    logging.info(
        "Churn prevention call complete for contact %s — satisfaction: %s, renewal: %s, next: %s",
        contact_id, satisfaction, likelihood, next_step,
    )

    note_lines = [
        f"Retention call completed — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"Contact: {contact_name}",
        f"Overall satisfaction: {satisfaction}",
        f"Likelihood to renew: {likelihood}",
        f"Requested next step: {next_step}",
    ]
    if primary_concern and primary_concern.strip().lower() not in ("none", "n/a", ""):
        note_lines.append(f"Primary concern: {primary_concern}")

    note_text = "\n".join(note_lines)

    try:
        add_contact_note(
            contact_id,
            subject="Retention call — Pinnacle Solutions",
            note_text=note_text,
        )
        logging.info("Retention note added to contact %s", contact_id)
    except Exception as e:
        logging.error("Failed to save retention note for contact %s: %s", contact_id, e)

    try:
        log_phone_call(
            contact_id,
            subject=f"Retention call — {contact_name}",
            description=note_text,
        )
        logging.info("Phone call logged for contact %s", contact_id)
    except Exception as e:
        logging.error("Failed to log phone call for contact %s: %s", contact_id, e)

    # Tailor the closing based on the requested next step
    if next_step == "speak-with-account-manager":
        closing = (
            f"Thank {contact_name} for their time and candid feedback. "
            "Let them know their dedicated account manager will reach out within one business "
            "day to schedule a conversation. Assure them that their satisfaction is our "
            "top priority."
        )
    elif next_step == "technical-support":
        closing = (
            f"Thank {contact_name} for their time. Let them know our technical support "
            "team will be in touch shortly to assist them. Remind them they can also reach "
            "support at any time by calling or emailing our support line."
        )
    elif next_step == "pricing-review":
        closing = (
            f"Thank {contact_name} for their transparency. Let them know our team will "
            "prepare a pricing review and reach out within two business days. Assure them "
            "we want to find an arrangement that works well for both sides."
        )
    else:
        closing = (
            f"Thank {contact_name} warmly for their time and positive feedback. "
            "Let them know we are always here if anything comes up. "
            "Wish them continued success."
        )

    call.hangup(final_instructions=closing)


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound churn prevention call for an at-risk Dynamics 365 contact."
    )
    parser.add_argument(
        "phone", help="Customer phone number to call (E.164 format, e.g. +15551234567)"
    )
    parser.add_argument(
        "--contact-id", required=True, help="Dynamics 365 contact ID (GUID)"
    )
    parser.add_argument("--name", required=True, help="Customer's full name")
    args = parser.parse_args()

    logging.info(
        "Initiating churn prevention call to %s (%s), contact %s",
        args.name, args.phone, args.contact_id,
    )

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "contact_id": args.contact_id,
            "contact_name": args.name,
        },
    )

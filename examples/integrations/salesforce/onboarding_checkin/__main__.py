import guava
import os
import logging
from guava import logging_utils
import argparse
import requests
from datetime import datetime, timezone


SALESFORCE_INSTANCE_URL = os.environ["SALESFORCE_INSTANCE_URL"]
SALESFORCE_ACCESS_TOKEN = os.environ["SALESFORCE_ACCESS_TOKEN"]
SF_HEADERS = {
    "Authorization": f"Bearer {SALESFORCE_ACCESS_TOKEN}",
    "Content-Type": "application/json",
}
API_BASE = f"{SALESFORCE_INSTANCE_URL}/services/data/v66.0"

ONBOARDING_STATUS_MAP = {
    "not started yet": "Not Started",
    "just getting started": "In Progress",
    "partially complete": "In Progress",
    "mostly done": "Nearly Complete",
    "fully set up": "Complete",
}


def get_account(account_id: str) -> dict | None:
    resp = requests.get(
        f"{API_BASE}/sobjects/Account/{account_id}",
        headers=SF_HEADERS,
        params={"fields": "Id,Name,Onboarding_Status__c,CustomerPriority__c"},
        timeout=10,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def update_account_onboarding(account_id: str, status: str, notes: str) -> None:
    resp = requests.patch(
        f"{API_BASE}/sobjects/Account/{account_id}",
        headers=SF_HEADERS,
        json={
            "Onboarding_Status__c": status,
            "Onboarding_Notes__c": notes,
        },
        timeout=10,
    )
    resp.raise_for_status()


def log_task(account_id: str, subject: str, description: str) -> None:
    payload = {
        "WhatId": account_id,
        "Subject": subject,
        "Description": description,
        "Status": "Completed",
        "Priority": "Normal",
        "Type": "Call",
        "TaskSubtype": "Call",
        "ActivityDate": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }
    resp = requests.post(
        f"{API_BASE}/sobjects/Task",
        headers=SF_HEADERS,
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()


def create_followup_task(account_id: str, subject: str, description: str, due_days: int = 3) -> None:
    """Creates an open follow-up Task due in the future."""
    due_date = (datetime.now(timezone.utc) + __import__("datetime").timedelta(days=due_days)).strftime("%Y-%m-%d")
    payload = {
        "WhatId": account_id,
        "Subject": subject,
        "Description": description,
        "Status": "Not Started",
        "Priority": "High",
        "Type": "Call",
        "ActivityDate": due_date,
    }
    resp = requests.post(
        f"{API_BASE}/sobjects/Task",
        headers=SF_HEADERS,
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()


agent = guava.Agent(
    name="Jamie",
    organization="Catalyst Software",
    purpose=(
        "to check in with new Catalyst Software customers to ensure their onboarding "
        "is on track and help them get the most out of the platform"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    account_id = call.get_variable("account_id")

    call.account_name = ""
    call.current_onboarding_status = ""
    try:
        account = get_account(account_id)
        if account:
            call.account_name = account.get("Name", "")
            call.current_onboarding_status = account.get("Onboarding_Status__c") or ""
    except Exception as e:
        logging.error("Failed to fetch Account %s pre-call: %s", account_id, e)

    call.reach_person(contact_full_name=contact_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    contact_name = call.get_variable("contact_name")
    account_id = call.get_variable("account_id")

    if outcome == "unavailable":
        logging.info(
            "Unable to reach %s for onboarding check-in on account %s.",
            contact_name, account_id,
        )
        try:
            log_task(
                account_id,
                subject="Onboarding check-in — contact unavailable",
                description=(
                    f"Onboarding check-in attempted — {contact_name} unavailable.\n"
                    f"Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
                ),
            )
        except Exception as e:
            logging.error("Failed to log missed-call Task: %s", e)

        call.hangup(
            final_instructions=(
                f"Leave a brief, friendly voicemail for {contact_name} from Catalyst Software. "
                "Let them know you're calling to check in on their onboarding and that you'll "
                "try again or they can reach out anytime. Keep it short and warm."
            )
        )
    elif outcome == "available":
        account_note = f" at {call.account_name}" if call.account_name else ""

        call.set_task(
            "record_checkin",
            objective=(
                f"Check in with {contact_name}{account_note} on their onboarding progress. "
                "Understand where they are in the setup process, surface any blockers, and "
                "ensure they feel confident and supported."
            ),
            checklist=[
                guava.Say(
                    f"Hi {contact_name}, this is Jamie from Catalyst Software. "
                    "I'm calling to check in and make sure your onboarding is going smoothly. "
                    "Do you have a couple of minutes?"
                ),
                guava.Field(
                    key="onboarding_progress",
                    field_type="multiple_choice",
                    description=(
                        "Ask: 'How would you describe where you are in the setup process so far?' "
                        "Map their answer to the closest option."
                    ),
                    choices=[
                        "not started yet",
                        "just getting started",
                        "partially complete",
                        "mostly done",
                        "fully set up",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="completed_steps",
                    field_type="text",
                    description=(
                        "Ask what they've managed to set up or complete so far. "
                        "Capture the key steps they've completed."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="blockers",
                    field_type="text",
                    description=(
                        "Ask: 'Is there anything that's slowing you down or that you're stuck on?' "
                        "Capture any specific blockers, confusion, or unresolved questions."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="support_needed",
                    field_type="multiple_choice",
                    description=(
                        "Ask what kind of help would be most useful right now."
                    ),
                    choices=[
                        "technical setup help",
                        "training / walkthrough session",
                        "documentation or guides",
                        "connect with an implementation specialist",
                        "no additional help needed",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="confidence_level",
                    field_type="multiple_choice",
                    description=(
                        "Ask: 'How confident are you feeling about using the platform day-to-day?' "
                    ),
                    choices=["very confident", "fairly confident", "somewhat unsure", "not confident at all"],
                    required=True,
                ),
            ],
        )


@agent.on_task_complete("record_checkin")
def on_done(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    account_id = call.get_variable("account_id")

    progress = call.get_field("onboarding_progress") or "partially complete"
    completed = call.get_field("completed_steps") or ""
    blockers = call.get_field("blockers") or ""
    support = call.get_field("support_needed") or "no additional help needed"
    confidence = call.get_field("confidence_level") or "fairly confident"

    new_status = ONBOARDING_STATUS_MAP.get(progress, "In Progress")

    notes_lines = [
        f"Onboarding check-in — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
        f"Contact: {contact_name}",
        f"Progress: {progress}",
        f"Confidence level: {confidence}",
        f"Support needed: {support}",
    ]
    if completed:
        notes_lines.append(f"Completed steps: {completed}")
    if blockers:
        notes_lines.append(f"Blockers: {blockers}")

    notes_str = "\n".join(notes_lines)

    logging.info(
        "Onboarding check-in complete for account %s — progress: %s, new status: %s",
        account_id, progress, new_status,
    )

    try:
        update_account_onboarding(account_id, new_status, notes_str)
        logging.info("Account %s onboarding status updated to: %s", account_id, new_status)
    except Exception as e:
        logging.error("Failed to update Account onboarding fields: %s", e)

    try:
        log_task(
            account_id,
            subject=f"Onboarding check-in — {progress}",
            description=notes_str,
        )
        logging.info("Check-in Task logged for account %s.", account_id)
    except Exception as e:
        logging.error("Failed to log Task: %s", e)

    needs_followup = (
        blockers
        or confidence in ("somewhat unsure", "not confident at all")
        or support != "no additional help needed"
    )

    if needs_followup:
        try:
            create_followup_task(
                account_id,
                subject=f"Onboarding follow-up — {support}",
                description=(
                    f"Follow up with {contact_name} on onboarding.\n"
                    f"Support needed: {support}\n"
                    + (f"Blockers: {blockers}" if blockers else "")
                ),
                due_days=2,
            )
            logging.info("Follow-up Task created for account %s.", account_id)
        except Exception as e:
            logging.error("Failed to create follow-up Task: %s", e)

    if progress == "fully set up" and confidence == "very confident":
        call.hangup(
            final_instructions=(
                f"Congratulate {contact_name} on completing onboarding! "
                "Tell them the team is thrilled to have them fully set up and to not hesitate "
                "to reach out anytime. Wish them great success with the platform."
            )
        )
    elif needs_followup:
        call.hangup(
            final_instructions=(
                f"Reassure {contact_name} that they're not alone. "
                f"Let them know the team will follow up within two business days with "
                f"help on '{support}'. "
                + (f"If they mentioned blockers, acknowledge them by name and say the team will address them. " if blockers else "")
                + "Thank them for their time and wish them a great day."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {contact_name} for the update. Let them know they're on track "
                "and that the Catalyst Software team is always here if they need anything. "
                "Wish them a great day."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound onboarding check-in call for a new Salesforce Account."
    )
    parser.add_argument("phone", help="Contact's phone number (E.164, e.g. +15551234567)")
    parser.add_argument("--account-id", required=True, help="Salesforce Account ID")
    parser.add_argument("--name", required=True, help="Full name of the contact to reach")
    args = parser.parse_args()

    logging.info(
        "Initiating onboarding check-in call to %s (%s) for account %s",
        args.name, args.phone, args.account_id,
    )

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "account_id": args.account_id,
            "contact_name": args.name,
        },
    )

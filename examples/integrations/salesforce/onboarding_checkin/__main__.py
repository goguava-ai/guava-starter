import guava
import os
import logging
import argparse
import requests
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)

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


class OnboardingCheckinController(guava.CallController):
    def __init__(self, account_id: str, contact_name: str):
        super().__init__()
        self.account_id = account_id
        self.contact_name = contact_name
        self.account_name = ""
        self.current_onboarding_status = ""

        try:
            account = get_account(account_id)
            if account:
                self.account_name = account.get("Name", "")
                self.current_onboarding_status = account.get("Onboarding_Status__c") or ""
        except Exception as e:
            logging.error("Failed to fetch Account %s pre-call: %s", account_id, e)

        self.set_persona(
            organization_name="Catalyst Software",
            agent_name="Jamie",
            agent_purpose=(
                "to check in with new Catalyst Software customers to ensure their onboarding "
                "is on track and help them get the most out of the platform"
            ),
        )

        self.reach_person(
            contact_full_name=contact_name,
            on_success=self.begin_checkin,
            on_failure=self.recipient_unavailable,
        )

    def begin_checkin(self):
        account_note = f" at {self.account_name}" if self.account_name else ""

        self.set_task(
            objective=(
                f"Check in with {self.contact_name}{account_note} on their onboarding progress. "
                "Understand where they are in the setup process, surface any blockers, and "
                "ensure they feel confident and supported."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.contact_name}, this is Jamie from Catalyst Software. "
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
            on_complete=self.record_checkin,
        )

    def record_checkin(self):
        progress = self.get_field("onboarding_progress") or "partially complete"
        completed = self.get_field("completed_steps") or ""
        blockers = self.get_field("blockers") or ""
        support = self.get_field("support_needed") or "no additional help needed"
        confidence = self.get_field("confidence_level") or "fairly confident"

        new_status = ONBOARDING_STATUS_MAP.get(progress, "In Progress")

        notes_lines = [
            f"Onboarding check-in — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
            f"Contact: {self.contact_name}",
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
            self.account_id, progress, new_status,
        )

        try:
            update_account_onboarding(self.account_id, new_status, notes_str)
            logging.info("Account %s onboarding status updated to: %s", self.account_id, new_status)
        except Exception as e:
            logging.error("Failed to update Account onboarding fields: %s", e)

        try:
            log_task(
                self.account_id,
                subject=f"Onboarding check-in — {progress}",
                description=notes_str,
            )
            logging.info("Check-in Task logged for account %s.", self.account_id)
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
                    self.account_id,
                    subject=f"Onboarding follow-up — {support}",
                    description=(
                        f"Follow up with {self.contact_name} on onboarding.\n"
                        f"Support needed: {support}\n"
                        + (f"Blockers: {blockers}" if blockers else "")
                    ),
                    due_days=2,
                )
                logging.info("Follow-up Task created for account %s.", self.account_id)
            except Exception as e:
                logging.error("Failed to create follow-up Task: %s", e)

        if progress == "fully set up" and confidence == "very confident":
            self.hangup(
                final_instructions=(
                    f"Congratulate {self.contact_name} on completing onboarding! "
                    "Tell them the team is thrilled to have them fully set up and to not hesitate "
                    "to reach out anytime. Wish them great success with the platform."
                )
            )
        elif needs_followup:
            self.hangup(
                final_instructions=(
                    f"Reassure {self.contact_name} that they're not alone. "
                    f"Let them know the team will follow up within two business days with "
                    f"help on '{support}'. "
                    + (f"If they mentioned blockers, acknowledge them by name and say the team will address them. " if blockers else "")
                    + "Thank them for their time and wish them a great day."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    f"Thank {self.contact_name} for the update. Let them know they're on track "
                    "and that the Catalyst Software team is always here if they need anything. "
                    "Wish them a great day."
                )
            )

    def recipient_unavailable(self):
        logging.info(
            "Unable to reach %s for onboarding check-in on account %s.",
            self.contact_name, self.account_id,
        )
        try:
            log_task(
                self.account_id,
                subject="Onboarding check-in — contact unavailable",
                description=(
                    f"Onboarding check-in attempted — {self.contact_name} unavailable.\n"
                    f"Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
                ),
            )
        except Exception as e:
            logging.error("Failed to log missed-call Task: %s", e)

        self.hangup(
            final_instructions=(
                f"Leave a brief, friendly voicemail for {self.contact_name} from Catalyst Software. "
                "Let them know you're calling to check in on their onboarding and that you'll "
                "try again or they can reach out anytime. Keep it short and warm."
            )
        )


if __name__ == "__main__":
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

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=OnboardingCheckinController(
            account_id=args.account_id,
            contact_name=args.name,
        ),
    )

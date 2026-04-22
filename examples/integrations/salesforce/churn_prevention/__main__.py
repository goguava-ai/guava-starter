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


def get_account(account_id: str) -> dict | None:
    resp = requests.get(
        f"{API_BASE}/sobjects/Account/{account_id}",
        headers=SF_HEADERS,
        params={"fields": "Id,Name,Type,Industry,OwnerId"},
        timeout=10,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def log_task(account_id: str, subject: str, description: str, priority: str = "High") -> None:
    """Logs a completed call Task against the Account."""
    payload = {
        "WhatId": account_id,
        "Subject": subject,
        "Description": description,
        "Status": "Completed",
        "Priority": priority,
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


def update_account_churn_risk(account_id: str, risk_level: str) -> None:
    """Updates the Churn_Risk__c custom field on the Account."""
    resp = requests.patch(
        f"{API_BASE}/sobjects/Account/{account_id}",
        headers=SF_HEADERS,
        json={"Churn_Risk__c": risk_level},
        timeout=10,
    )
    resp.raise_for_status()


RISK_MAP = {
    "very dissatisfied": "High",
    "dissatisfied": "High",
    "neutral": "Medium",
    "satisfied": "Low",
    "very satisfied": "Low",
}


class ChurnPreventionController(guava.CallController):
    def __init__(self, account_id: str, contact_name: str):
        super().__init__()
        self.account_id = account_id
        self.contact_name = contact_name
        self.account_name = ""

        try:
            account = get_account(account_id)
            if account:
                self.account_name = account.get("Name", "")
        except Exception as e:
            logging.error("Failed to fetch Account %s pre-call: %s", account_id, e)

        self.set_persona(
            organization_name="Crestview Technologies",
            agent_name="Jordan",
            agent_purpose=(
                "to proactively reach out to at-risk customers, understand their concerns, "
                "and help Crestview Technologies retain their business"
            ),
        )

        self.reach_person(
            contact_full_name=contact_name,
            on_success=self.begin_retention_call,
            on_failure=self.recipient_unavailable,
        )

    def begin_retention_call(self):
        account_note = f" at {self.account_name}" if self.account_name else ""

        self.set_task(
            objective=(
                f"Check in with {self.contact_name}{account_note} to understand their "
                "experience and address any concerns that may be putting the relationship at risk."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.contact_name}, this is Jordan calling from Crestview Technologies. "
                    "I'm reaching out personally because we value your partnership and want to "
                    "make sure everything is going well on your end."
                ),
                guava.Field(
                    key="satisfaction",
                    field_type="multiple_choice",
                    description=(
                        "Ask how satisfied they are with Crestview Technologies overall. "
                        "Be genuine and conversational."
                    ),
                    choices=["very satisfied", "satisfied", "neutral", "dissatisfied", "very dissatisfied"],
                    required=True,
                ),
                guava.Field(
                    key="primary_concern",
                    field_type="text",
                    description=(
                        "Ask if there are any specific concerns or pain points they'd like to share. "
                        "Listen carefully and capture the full detail of any issues raised."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="likelihood_to_renew",
                    field_type="multiple_choice",
                    description=(
                        "Ask how likely they are to renew or continue the relationship. "
                        "'When it comes time to renew, how are you feeling about continuing with us?'"
                    ),
                    choices=["very likely", "likely", "unsure", "unlikely", "not renewing"],
                    required=True,
                ),
                guava.Field(
                    key="requested_action",
                    field_type="multiple_choice",
                    description=(
                        "Ask what would be most helpful as a next step. "
                        "'What would be most valuable for you right now?'"
                    ),
                    choices=[
                        "speak with a customer success manager",
                        "product training or onboarding help",
                        "pricing review",
                        "technical support escalation",
                        "no action needed",
                    ],
                    required=True,
                ),
            ],
            on_complete=self.log_outcome,
        )

    def log_outcome(self):
        satisfaction = self.get_field("satisfaction") or "unknown"
        concern = self.get_field("primary_concern") or ""
        likelihood = self.get_field("likelihood_to_renew") or "unknown"
        action = self.get_field("requested_action") or "no action needed"

        risk_level = RISK_MAP.get(satisfaction, "Medium")
        logging.info(
            "Churn prevention call complete for account %s — satisfaction: %s, risk: %s",
            self.account_id, satisfaction, risk_level,
        )

        description_lines = [
            f"Churn prevention outreach — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
            f"Contact: {self.contact_name}",
            f"Satisfaction: {satisfaction}",
            f"Renewal likelihood: {likelihood}",
            f"Requested action: {action}",
        ]
        if concern:
            description_lines.append(f"Primary concern: {concern}")

        try:
            log_task(
                self.account_id,
                subject=f"Churn prevention call — {satisfaction}",
                description="\n".join(description_lines),
                priority="High" if risk_level == "High" else "Normal",
            )
            logging.info("Task logged for account %s.", self.account_id)
        except Exception as e:
            logging.error("Failed to log Task for account %s: %s", self.account_id, e)

        try:
            update_account_churn_risk(self.account_id, risk_level)
            logging.info("Updated Churn_Risk__c to %s for account %s.", risk_level, self.account_id)
        except Exception as e:
            logging.warning(
                "Could not update Churn_Risk__c (field may not exist in this org): %s", e
            )

        if likelihood in ("unlikely", "not renewing"):
            self.hangup(
                final_instructions=(
                    f"Express genuine concern and gratitude to {self.contact_name}. "
                    "Let them know their feedback is important and a customer success manager will "
                    "follow up personally within one business day to address their concerns. "
                    "Thank them sincerely for their time."
                )
            )
        elif action != "no action needed":
            self.hangup(
                final_instructions=(
                    f"Thank {self.contact_name} for their candid feedback. "
                    f"Confirm that you've noted their request for '{action}' and that the right "
                    "person from the team will be in touch. Express confidence that we can make "
                    "things right. Wish them a great day."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    f"Thank {self.contact_name} for their time and for sharing their experience. "
                    "Let them know Crestview Technologies appreciates their business and is always "
                    "here if they need anything. Wish them a great day."
                )
            )

    def recipient_unavailable(self):
        logging.info("Unable to reach %s for churn prevention call on account %s.",
                     self.contact_name, self.account_id)
        try:
            log_task(
                self.account_id,
                subject="Churn prevention call — contact unavailable",
                description=(
                    f"Attempted outreach to {self.contact_name} — contact unavailable, voicemail left.\n"
                    f"Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
                ),
                priority="High",
            )
        except Exception as e:
            logging.error("Failed to log missed-call Task: %s", e)

        self.hangup(
            final_instructions=(
                f"Leave a warm, concise voicemail for {self.contact_name} on behalf of Crestview "
                "Technologies. Let them know you're calling to check in and make sure everything "
                "is going well. Ask them to call back at their convenience. Keep it brief."
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Outbound churn prevention call for an at-risk Salesforce Account."
    )
    parser.add_argument("phone", help="Contact's phone number (E.164, e.g. +15551234567)")
    parser.add_argument("--account-id", required=True, help="Salesforce Account ID")
    parser.add_argument("--name", required=True, help="Full name of the contact to reach")
    args = parser.parse_args()

    logging.info(
        "Initiating churn prevention call to %s (%s) for account %s",
        args.name, args.phone, args.account_id,
    )

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=ChurnPreventionController(
            account_id=args.account_id,
            contact_name=args.name,
        ),
    )

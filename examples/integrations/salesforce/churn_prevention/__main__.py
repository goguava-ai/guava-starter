import argparse
import logging
import os
from datetime import datetime, timezone

import guava
import requests
from guava import logging_utils

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


agent = guava.Agent(
    name="Jordan",
    organization="Crestview Technologies",
    purpose=(
        "to proactively reach out to at-risk customers, understand their concerns, "
        "and help Crestview Technologies retain their business"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    account_id = call.get_variable("account_id")

    account_name = ""
    try:
        account = get_account(account_id)
        if account:
            account_name = account.get("Name", "")
    except Exception as e:
        logging.error("Failed to fetch Account %s pre-call: %s", account_id, e)

    call.set_variable("account_name", account_name)
    call.reach_person(contact_full_name=contact_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    contact_name = call.get_variable("contact_name")
    account_id = call.get_variable("account_id")

    if outcome == "unavailable":
        logging.info("Unable to reach %s for churn prevention call on account %s.",
                     contact_name, account_id)
        try:
            log_task(
                account_id,
                subject="Churn prevention call — contact unavailable",
                description=(
                    f"Attempted outreach to {contact_name} — contact unavailable, voicemail left.\n"
                    f"Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
                ),
                priority="High",
            )
        except Exception as e:
            logging.error("Failed to log missed-call Task: %s", e)

        call.hangup(
            final_instructions=(
                f"Leave a warm, concise voicemail for {contact_name} on behalf of Crestview "
                "Technologies. Let them know you're calling to check in and make sure everything "
                "is going well. Ask them to call back at their convenience. Keep it brief."
            )
        )
    elif outcome == "available":
        account_name = call.get_variable("account_name") or ""
        account_note = f" at {account_name}" if account_name else ""

        call.set_task(
            "log_outcome",
            objective=(
                f"Check in with {contact_name}{account_note} to understand their "
                "experience and address any concerns that may be putting the relationship at risk."
            ),
            checklist=[
                guava.Say(
                    f"Hi {contact_name}, this is Jordan calling from Crestview Technologies. "
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
        )


@agent.on_task_complete("log_outcome")
def on_done(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    account_id = call.get_variable("account_id")

    satisfaction = call.get_field("satisfaction") or "unknown"
    concern = call.get_field("primary_concern") or ""
    likelihood = call.get_field("likelihood_to_renew") or "unknown"
    action = call.get_field("requested_action") or "no action needed"

    risk_level = RISK_MAP.get(satisfaction, "Medium")
    logging.info(
        "Churn prevention call complete for account %s — satisfaction: %s, risk: %s",
        account_id, satisfaction, risk_level,
    )

    description_lines = [
        f"Churn prevention outreach — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
        f"Contact: {contact_name}",
        f"Satisfaction: {satisfaction}",
        f"Renewal likelihood: {likelihood}",
        f"Requested action: {action}",
    ]
    if concern:
        description_lines.append(f"Primary concern: {concern}")

    try:
        log_task(
            account_id,
            subject=f"Churn prevention call — {satisfaction}",
            description="\n".join(description_lines),
            priority="High" if risk_level == "High" else "Normal",
        )
        logging.info("Task logged for account %s.", account_id)
    except Exception as e:
        logging.error("Failed to log Task for account %s: %s", account_id, e)

    try:
        update_account_churn_risk(account_id, risk_level)
        logging.info("Updated Churn_Risk__c to %s for account %s.", risk_level, account_id)
    except Exception as e:
        logging.warning(
            "Could not update Churn_Risk__c (field may not exist in this org): %s", e
        )

    if likelihood in ("unlikely", "not renewing"):
        call.hangup(
            final_instructions=(
                f"Express genuine concern and gratitude to {contact_name}. "
                "Let them know their feedback is important and a customer success manager will "
                "follow up personally within one business day to address their concerns. "
                "Thank them sincerely for their time."
            )
        )
    elif action != "no action needed":
        call.hangup(
            final_instructions=(
                f"Thank {contact_name} for their candid feedback. "
                f"Confirm that you've noted their request for '{action}' and that the right "
                "person from the team will be in touch. Express confidence that we can make "
                "things right. Wish them a great day."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {contact_name} for their time and for sharing their experience. "
                "Let them know Crestview Technologies appreciates their business and is always "
                "here if they need anything. Wish them a great day."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
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

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "account_id": args.account_id,
            "contact_name": args.name,
        },
    )

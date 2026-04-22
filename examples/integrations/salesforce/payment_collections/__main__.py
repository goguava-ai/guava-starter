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
        params={"fields": "Id,Name,Phone"},
        timeout=10,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def get_overdue_opportunities(account_id: str) -> list:
    """Returns Closed Won opportunities with an overdue payment date for the account."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    q = (
        f"SELECT Id, Name, Amount, CloseDate FROM Opportunity "
        f"WHERE AccountId = '{account_id}' "
        f"AND StageName = 'Closed Won' "
        f"AND CloseDate < {today} "
        f"AND Pricebook2Id != null "
        f"LIMIT 5"
    )
    resp = requests.get(
        f"{API_BASE}/query",
        headers=SF_HEADERS,
        params={"q": q},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("records", [])


def log_collections_task(account_id: str, subject: str, description: str, priority: str) -> None:
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


def update_account_collections_status(account_id: str, status: str) -> None:
    """Updates Collections_Status__c custom field on Account."""
    resp = requests.patch(
        f"{API_BASE}/sobjects/Account/{account_id}",
        headers=SF_HEADERS,
        json={"Collections_Status__c": status},
        timeout=10,
    )
    resp.raise_for_status()


OUTCOME_STATUS = {
    "paying now": "Payment Received",
    "payment plan requested": "Payment Plan",
    "promised to pay later": "Promise to Pay",
    "disputes the amount": "In Dispute",
    "refused to pay": "Escalated",
}


agent = guava.Agent(
    name="Alex",
    organization="Crestline Financial",
    purpose=(
        "to assist customers with outstanding account balances and help them "
        "resolve overdue payments for Crestline Financial"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    account_id = call.get_variable("account_id")

    call.set_variable("account_name", "")
    try:
        account = get_account(account_id)
        if account:
            call.set_variable("account_name", account.get("Name", ""))
    except Exception as e:
        logging.error("Failed to fetch Account %s pre-call: %s", account_id, e)

    call.reach_person(contact_full_name=contact_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    contact_name = call.get_variable("contact_name")
    account_id = call.get_variable("account_id")
    overdue_amount = call.get_variable("overdue_amount")

    if outcome == "unavailable":
        logging.info(
            "Unable to reach %s for collections call on account %s.",
            contact_name, account_id,
        )
        try:
            log_collections_task(
                account_id,
                subject="Collections call — contact unavailable",
                description=(
                    f"Collections outreach attempted — {contact_name} unavailable, voicemail left.\n"
                    f"Overdue amount: {overdue_amount}\n"
                    f"Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
                ),
                priority="High",
            )
        except Exception as e:
            logging.error("Failed to log missed-call Task: %s", e)

        call.hangup(
            final_instructions=(
                f"Leave a professional, non-threatening voicemail for {contact_name} "
                "from Crestline Financial. Mention that you're calling regarding their account "
                "and ask them to call back at their earliest convenience. "
                "Do not mention specific dollar amounts in the voicemail."
            )
        )
    elif outcome == "available":
        account_name = call.get_variable("account_name", "")
        account_note = f" at {account_name}" if account_name else ""

        call.set_task(
            "record_outcome",
            objective=(
                f"Speak with {contact_name}{account_note} about an outstanding balance "
                f"of {overdue_amount}. Be professional, empathetic, and non-confrontational. "
                "Help them find a resolution that works for both parties."
            ),
            checklist=[
                guava.Say(
                    f"Hi, may I speak with {contact_name}? "
                    f"This is Alex calling from Crestline Financial regarding your account."
                ),
                guava.Field(
                    key="acknowledges_balance",
                    field_type="multiple_choice",
                    description=(
                        f"Inform them there is an outstanding balance of {overdue_amount} on their account "
                        "and ask if they are aware of it. Capture their response."
                    ),
                    choices=["yes, aware", "no, not aware", "disputes the amount"],
                    required=True,
                ),
                guava.Field(
                    key="payment_outcome",
                    field_type="multiple_choice",
                    description=(
                        "Ask how they'd like to resolve the balance. Present the options professionally."
                    ),
                    choices=[
                        "paying now",
                        "payment plan requested",
                        "promised to pay later",
                        "disputes the amount",
                        "refused to pay",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="promise_date",
                    field_type="text",
                    description=(
                        "If they promised to pay later, ask for a specific date by which they'll pay. "
                        "Confirm it back to them. Skip if paying now or setting up a payment plan."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="dispute_detail",
                    field_type="text",
                    description=(
                        "If they dispute the amount, ask them to describe the discrepancy. "
                        "Capture their explanation in detail."
                    ),
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("record_outcome")
def on_done(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    account_id = call.get_variable("account_id")
    overdue_amount = call.get_variable("overdue_amount")

    acknowledges = call.get_field("acknowledges_balance") or "yes, aware"
    outcome = call.get_field("payment_outcome") or "promised to pay later"
    promise_date = call.get_field("promise_date") or ""
    dispute_detail = call.get_field("dispute_detail") or ""

    collections_status = OUTCOME_STATUS.get(outcome, "Promise to Pay")
    priority = "High" if outcome in ("refused to pay", "disputes the amount") else "Normal"

    description_lines = [
        f"Collections call — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
        f"Contact: {contact_name}",
        f"Overdue amount: {overdue_amount}",
        f"Acknowledged balance: {acknowledges}",
        f"Outcome: {outcome}",
    ]
    if promise_date:
        description_lines.append(f"Promise to pay by: {promise_date}")
    if dispute_detail:
        description_lines.append(f"Dispute details: {dispute_detail}")

    logging.info(
        "Collections call complete for account %s — outcome: %s, status: %s",
        account_id, outcome, collections_status,
    )

    try:
        log_collections_task(
            account_id,
            subject=f"Collections call — {outcome}",
            description="\n".join(description_lines),
            priority=priority,
        )
        logging.info("Task logged for account %s.", account_id)
    except Exception as e:
        logging.error("Failed to log Task: %s", e)

    try:
        update_account_collections_status(account_id, collections_status)
        logging.info("Updated Collections_Status__c to '%s' for account %s.", collections_status, account_id)
    except Exception as e:
        logging.warning("Could not update Collections_Status__c (field may not exist): %s", e)

    if outcome == "paying now":
        call.hangup(
            final_instructions=(
                f"Thank {contact_name} for taking care of this right away. "
                "Let them know they'll receive a payment confirmation via email. "
                "Wish them a great day."
            )
        )
    elif outcome == "payment plan requested":
        call.hangup(
            final_instructions=(
                f"Thank {contact_name} for working with us. "
                "Let them know a member of the billing team will reach out within one business day "
                "to arrange a payment plan. Reassure them that we'll find a workable solution."
            )
        )
    elif outcome == "promised to pay later":
        call.hangup(
            final_instructions=(
                f"Thank {contact_name} and confirm the promise date back to them: "
                f"'{promise_date}'. "
                "Let them know we'll follow up if the payment hasn't been received by then. "
                "Wish them a good day."
            )
        )
    elif outcome == "disputes the amount":
        call.hangup(
            final_instructions=(
                f"Thank {contact_name} for letting us know. "
                "Let them know their dispute has been noted and a billing specialist will review "
                "it and follow up within two business days. Apologize for any confusion."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {contact_name} for their time. Let them know this matter will be "
                "escalated to our accounts receivable team who will be in touch. "
                "Remain professional and non-confrontational."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound payment collections call for a Salesforce Account."
    )
    parser.add_argument("phone", help="Contact's phone number (E.164, e.g. +15551234567)")
    parser.add_argument("--account-id", required=True, help="Salesforce Account ID")
    parser.add_argument("--name", required=True, help="Full name of the contact")
    parser.add_argument("--amount", required=True, help="Overdue balance to collect (e.g. '$4,200.00')")
    args = parser.parse_args()

    logging.info(
        "Initiating collections call to %s (%s) for account %s — balance: %s",
        args.name, args.phone, args.account_id, args.amount,
    )

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "account_id": args.account_id,
            "contact_name": args.name,
            "overdue_amount": args.amount,
        },
    )

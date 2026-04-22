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


class PaymentCollectionsController(guava.CallController):
    def __init__(self, account_id: str, contact_name: str, overdue_amount: str):
        super().__init__()
        self.account_id = account_id
        self.contact_name = contact_name
        self.overdue_amount = overdue_amount
        self.account_name = ""

        try:
            account = get_account(account_id)
            if account:
                self.account_name = account.get("Name", "")
        except Exception as e:
            logging.error("Failed to fetch Account %s pre-call: %s", account_id, e)

        self.set_persona(
            organization_name="Crestline Financial",
            agent_name="Alex",
            agent_purpose=(
                "to assist customers with outstanding account balances and help them "
                "resolve overdue payments for Crestline Financial"
            ),
        )

        self.reach_person(
            contact_full_name=contact_name,
            on_success=self.begin_collections_call,
            on_failure=self.recipient_unavailable,
        )

    def begin_collections_call(self):
        account_note = f" at {self.account_name}" if self.account_name else ""

        self.set_task(
            objective=(
                f"Speak with {self.contact_name}{account_note} about an outstanding balance "
                f"of {self.overdue_amount}. Be professional, empathetic, and non-confrontational. "
                "Help them find a resolution that works for both parties."
            ),
            checklist=[
                guava.Say(
                    f"Hi, may I speak with {self.contact_name}? "
                    f"This is Alex calling from Crestline Financial regarding your account."
                ),
                guava.Field(
                    key="acknowledges_balance",
                    field_type="multiple_choice",
                    description=(
                        f"Inform them there is an outstanding balance of {self.overdue_amount} on their account "
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
            on_complete=self.record_outcome,
        )

    def record_outcome(self):
        acknowledges = self.get_field("acknowledges_balance") or "yes, aware"
        outcome = self.get_field("payment_outcome") or "promised to pay later"
        promise_date = self.get_field("promise_date") or ""
        dispute_detail = self.get_field("dispute_detail") or ""

        collections_status = OUTCOME_STATUS.get(outcome, "Promise to Pay")
        priority = "High" if outcome in ("refused to pay", "disputes the amount") else "Normal"

        description_lines = [
            f"Collections call — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
            f"Contact: {self.contact_name}",
            f"Overdue amount: {self.overdue_amount}",
            f"Acknowledged balance: {acknowledges}",
            f"Outcome: {outcome}",
        ]
        if promise_date:
            description_lines.append(f"Promise to pay by: {promise_date}")
        if dispute_detail:
            description_lines.append(f"Dispute details: {dispute_detail}")

        logging.info(
            "Collections call complete for account %s — outcome: %s, status: %s",
            self.account_id, outcome, collections_status,
        )

        try:
            log_collections_task(
                self.account_id,
                subject=f"Collections call — {outcome}",
                description="\n".join(description_lines),
                priority=priority,
            )
            logging.info("Task logged for account %s.", self.account_id)
        except Exception as e:
            logging.error("Failed to log Task: %s", e)

        try:
            update_account_collections_status(self.account_id, collections_status)
            logging.info("Updated Collections_Status__c to '%s' for account %s.", collections_status, self.account_id)
        except Exception as e:
            logging.warning("Could not update Collections_Status__c (field may not exist): %s", e)

        if outcome == "paying now":
            self.hangup(
                final_instructions=(
                    f"Thank {self.contact_name} for taking care of this right away. "
                    "Let them know they'll receive a payment confirmation via email. "
                    "Wish them a great day."
                )
            )
        elif outcome == "payment plan requested":
            self.hangup(
                final_instructions=(
                    f"Thank {self.contact_name} for working with us. "
                    "Let them know a member of the billing team will reach out within one business day "
                    "to arrange a payment plan. Reassure them that we'll find a workable solution."
                )
            )
        elif outcome == "promised to pay later":
            self.hangup(
                final_instructions=(
                    f"Thank {self.contact_name} and confirm the promise date back to them: "
                    f"'{promise_date}'. "
                    "Let them know we'll follow up if the payment hasn't been received by then. "
                    "Wish them a good day."
                )
            )
        elif outcome == "disputes the amount":
            self.hangup(
                final_instructions=(
                    f"Thank {self.contact_name} for letting us know. "
                    "Let them know their dispute has been noted and a billing specialist will review "
                    "it and follow up within two business days. Apologize for any confusion."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    f"Thank {self.contact_name} for their time. Let them know this matter will be "
                    "escalated to our accounts receivable team who will be in touch. "
                    "Remain professional and non-confrontational."
                )
            )

    def recipient_unavailable(self):
        logging.info(
            "Unable to reach %s for collections call on account %s.",
            self.contact_name, self.account_id,
        )
        try:
            log_collections_task(
                self.account_id,
                subject="Collections call — contact unavailable",
                description=(
                    f"Collections outreach attempted — {self.contact_name} unavailable, voicemail left.\n"
                    f"Overdue amount: {self.overdue_amount}\n"
                    f"Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
                ),
                priority="High",
            )
        except Exception as e:
            logging.error("Failed to log missed-call Task: %s", e)

        self.hangup(
            final_instructions=(
                f"Leave a professional, non-threatening voicemail for {self.contact_name} "
                "from Crestline Financial. Mention that you're calling regarding their account "
                "and ask them to call back at their earliest convenience. "
                "Do not mention specific dollar amounts in the voicemail."
            )
        )


if __name__ == "__main__":
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

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=PaymentCollectionsController(
            account_id=args.account_id,
            contact_name=args.name,
            overdue_amount=args.amount,
        ),
    )

import argparse
import json
import logging
import os
from datetime import datetime, timezone

import guava
from guava import logging_utils

agent = guava.Agent(
    name="Casey",
    organization="Springfield Municipal Utilities",
    purpose=(
        "notify residents of impending utility service shutoffs, explain available "
        "options including payment plans and hardship programs, and collect "
        "structured payment commitments"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(contact_full_name=call.get_variable("resident_name"))


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    if outcome == "unavailable":
        logging.info(
            "Resident %s was unavailable for utility shutoff warning call on account %s.",
            call.get_variable("resident_name"),
            call.get_variable("account_number"),
        )
    elif outcome == "available":
        resident_name = call.get_variable("resident_name")
        account_number = call.get_variable("account_number")
        amount_owed = call.get_variable("amount_owed")
        shutoff_date = call.get_variable("shutoff_date")
        call.set_task(
            "notification",
            objective=(
                f"You are calling on behalf of Springfield Municipal Utilities to notify "
                f"{resident_name} that their utility account (account number "
                f"{account_number}) has a past-due balance of {amount_owed} and is "
                f"scheduled for service shutoff on {shutoff_date}. Clearly communicate "
                "the urgency of the situation while maintaining a respectful and neutral tone. "
                "Explain that options are available including full payment, a payment plan, "
                "disputing the balance, or applying for a hardship assistance program. "
                "Collect the resident's intended course of action and any relevant commitments."
            ),
            checklist=[
                guava.Say(
                    f"Hello, this is Casey calling from Springfield Municipal Utilities. "
                    f"I'm reaching out regarding account number {account_number}. "
                    f"Our records show a past-due balance of {amount_owed} on this account. "
                    f"If this balance is not resolved, service is currently scheduled to be "
                    f"shut off on {shutoff_date}. We want to make sure you are aware of "
                    "this and that you know about the options available to you, including "
                    "payment plans and hardship assistance programs."
                ),
                guava.Field(
                    key="shutoff_date_acknowledged",
                    description=(
                        "Confirm that the resident has heard and acknowledged the scheduled "
                        "shutoff date and the past-due balance amount."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="payment_intention",
                    description=(
                        "Ask the resident how they intend to address the balance. Options are: "
                        "pay the full amount now, set up a payment plan, dispute the balance, "
                        "or apply for a hardship assistance program."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="payment_amount_commitment",
                    description=(
                        "If the resident intends to make a payment or set up a payment plan, "
                        "ask what amount they are able to commit to paying."
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="payment_date_commitment",
                    description=(
                        "If the resident intends to make a payment or start a payment plan, "
                        "ask by what date they expect to make the first payment."
                    ),
                    field_type="date",
                    required=False,
                ),
                guava.Field(
                    key="hardship_program_interest",
                    description=(
                        "If the resident expresses interest in the hardship assistance program "
                        "or indicates financial difficulty, ask whether they would like "
                        "information on how to apply."
                    ),
                    field_type="text",
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("notification")
def on_done(call: guava.Call) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "resident_name": call.get_variable("resident_name"),
        "account_number": call.get_variable("account_number"),
        "amount_owed": call.get_variable("amount_owed"),
        "shutoff_date": call.get_variable("shutoff_date"),
        "fields": {
            "shutoff_date_acknowledged": call.get_field("shutoff_date_acknowledged"),
            "payment_intention": call.get_field("payment_intention"),
            "payment_amount_commitment": call.get_field("payment_amount_commitment"),
            "payment_date_commitment": call.get_field("payment_date_commitment"),
            "hardship_program_interest": call.get_field("hardship_program_interest"),
        },
    }
    print(json.dumps(results, indent=2))
    call.hangup(
        final_instructions=(
            "Thank the resident for their time and for speaking with you. Based on their "
            "stated intention, summarize the next steps clearly — for example, confirm the "
            "payment amount and date if applicable, or let them know a representative will "
            "follow up about a payment plan or hardship application. Remind them that "
            "Springfield Municipal Utilities customer service is available to assist them "
            "further. End the call respectfully."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound utility shutoff warning call for Springfield Municipal Utilities."
    )
    parser.add_argument("phone", help="Resident phone number to call (E.164 format).")
    parser.add_argument("--name", required=True, help="Full name of the account holder.")
    parser.add_argument("--account-number", required=True, help="Utility account number.")
    parser.add_argument(
        "--amount-owed",
        required=True,
        help='Past-due balance on the account (e.g., "$142.50").',
    )
    parser.add_argument(
        "--shutoff-date",
        required=True,
        help='Scheduled shutoff date (e.g., "March 5, 2026").',
    )
    args = parser.parse_args()

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "resident_name": args.name,
            "account_number": args.account_number,
            "amount_owed": args.amount_owed,
            "shutoff_date": args.shutoff_date,
        },
    )

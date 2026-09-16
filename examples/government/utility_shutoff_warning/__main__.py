# SDK conformance: guava-sdk 0.43.0 (2026-09-15)
import argparse
import json
import logging
import os
from datetime import datetime, timezone

import guava
from guava import logging_utils
from guava.helpers.llm import IntentRecognizer
from guava.events import BotSessionEnded, OutboundCallFailed


# ---------------------------------------------------------------------------
# Mock API — simulates an account balance backend for demo purposes
# ---------------------------------------------------------------------------

HARDSHIP_LINE = "+15551000500"
BILLING_LINE = "+15551000501"

MOCK_ACCOUNTS = {
    "SMU-440012": {
        "name": "Patricia Alvarez",
        "dob": "1979-04-18",
        "balance": "$287.43",
        "shutoff_date": "August 15, 2026",
        "months_past_due": 3,
        "payment_plan_eligible": True,
        "hardship_eligible": True,
    },
    "SMU-440078": {
        "name": "Robert Nguyen",
        "dob": "1986-09-30",
        "balance": "$142.50",
        "shutoff_date": "August 20, 2026",
        "months_past_due": 2,
        "payment_plan_eligible": True,
        "hardship_eligible": False,
    },
    "SMU-440195": {
        "name": "Karen Thompson",
        "dob": "1963-12-03",
        "balance": "$523.17",
        "shutoff_date": "August 10, 2026",
        "months_past_due": 5,
        "payment_plan_eligible": True,
        "hardship_eligible": True,
    },
}


def verify_account(account_number, dob):
    account = MOCK_ACCOUNTS.get(account_number)
    if account and account["dob"] == dob:
        return account
    return None


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

agent = guava.Agent(
    name="Kerry",
    organization="Springfield Municipal Utilities",
    purpose=(
        "verify account holder identity, notify them of impending utility "
        "shutoff with balance details, and route them to the appropriate "
        "payment or assistance path"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
    "speak_to_billing": "The caller wants to speak to a billing representative or customer service agent",
})


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(
        contact_full_name=call.get_variable("resident_name"),
        voicemail_message=(
            f"Hi, this is Kerry from Springfield Municipal Utilities calling for "
            f"{call.get_variable('resident_name')}. We have an important notice "
            f"regarding your utility account. Please call us back at "
            f"1-800-555-0500 as soon as possible. Thank you."
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    resident_name = call.get_variable("resident_name")

    if outcome == "available":
        call.set_task(
            "verify_identity",
            objective=(
                f"Verify the identity of {resident_name} before sharing any "
                f"account balance or shutoff details. Ask for their date of birth. "
                f"Do not discuss account balances, shutoff dates, or payment options "
                f"until identity is confirmed."
            ),
            checklist=[
                guava.Say(
                    "I have an important notice regarding your utility account. "
                    "Before I can share any details, I need to verify your identity "
                    "with a quick question."
                ),
                guava.Field(
                    key="dob",
                    description="The account holder's date of birth for identity verification",
                    field_type="text",
                    required=True,
                ),
            ],
        )
    elif outcome == "do_not_contact":
        logging.info("Resident %s requested no further contact.", resident_name)
        call.hangup(
            final_instructions=(
                "Acknowledge their request. Let them know they will not be contacted "
                "again by phone. Note that important account notices will still be "
                "sent by mail, and politely say goodbye."
            )
        )
    elif outcome == "wrong_number":
        logging.info("Wrong number for %s.", resident_name)
        call.hangup(final_instructions="Apologize for the mistake and wish them well, and politely say goodbye.")
    else:
        logging.info("Could not reach %s (outcome: %s).", resident_name, outcome)
        call.hangup()


@agent.on_task_complete("verify_identity")
def on_identity_verified(call: guava.Call) -> None:
    account_number = call.get_variable("account_number")
    dob = call.get_field("dob")
    account = verify_account(account_number, dob)

    if account is None:
        logging.warning("Identity verification failed for account %s.", account_number)
        call.hangup(
            final_instructions=(
                "Let them know the date of birth provided does not match our records "
                "for this account. For security, you cannot share account details. "
                "Suggest they call Springfield Municipal Utilities at 1-800-555-0500 "
                "with their account documents handy, and politely say goodbye."
            )
        )
        return

    call.set_variable("balance", account["balance"])
    call.set_variable("shutoff_date", account["shutoff_date"])
    call.set_variable("hardship_eligible", str(account["hardship_eligible"]))

    call.add_info("account_details", {
        "account_number": account_number,
        "balance": account["balance"],
        "shutoff_date": account["shutoff_date"],
        "months_past_due": account["months_past_due"],
        "payment_plan_eligible": account["payment_plan_eligible"],
        "hardship_eligible": account["hardship_eligible"],
    })

    resident_name = call.get_variable("resident_name")

    call.set_task(
        "present_balance",
        objective=(
            f"Identity verified. Inform {resident_name} that their utility account "
            f"(account {account_number}) has a past-due balance of {account['balance']} "
            f"and is scheduled for service shutoff on {account['shutoff_date']}. "
            f"Clearly communicate the urgency while maintaining a respectful tone. "
            f"Explain the available options: full payment, payment plan, hardship "
            f"assistance program, or disputing the balance. Collect their intended "
            f"course of action. "
            f"Do NOT share specific account details beyond balance and shutoff date "
            f"unless the customer asks."
        ),
        checklist=[
            guava.Say(
                f"Thank you, your identity has been verified. I'm calling because "
                f"your utility account has a past-due balance of {account['balance']}. "
                f"If this balance is not resolved, service is scheduled to be shut "
                f"off on {account['shutoff_date']}. I want to make sure you know "
                f"about the options available to you."
            ),
            guava.Field(
                key="balance_acknowledged",
                description=(
                    "Confirm that the resident has heard and acknowledged the "
                    "past-due balance and scheduled shutoff date"
                ),
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="payment_path",
                description="How the resident intends to address the balance",
                field_type="multiple_choice",
                choices=["will_pay", "payment_plan", "hardship", "dispute"],
                required=True,
            ),
        ],
    )


@agent.on_task_complete("present_balance")
def on_balance_presented(call: guava.Call) -> None:
    payment_path = call.get_field("payment_path")
    resident_name = call.get_variable("resident_name")

    if payment_path == "will_pay":
        call.set_task(
            "payment_info",
            objective=(
                f"{resident_name} intends to pay the balance. Provide payment "
                f"portal information: payments can be made online at "
                f"springfieldutilities.gov/pay, by phone at 1-800-555-0500, or "
                f"in person at any Springfield Municipal Utilities office. "
                f"Confirm when they plan to make the payment."
            ),
            checklist=[
                guava.Field(
                    key="payment_date_commitment",
                    description="When the resident plans to make the payment",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="payment_method",
                    description="How the resident plans to make the payment",
                    field_type="multiple_choice",
                    choices=["online", "by phone", "in person"],
                    required=True,
                ),
            ],
        )
    elif payment_path == "payment_plan":
        call.set_task(
            "payment_plan_info",
            objective=(
                f"{resident_name} is interested in a payment plan. Explain that "
                f"Springfield Municipal Utilities offers plans that split the "
                f"balance into 3, 6, or 12 monthly installments. The shutoff "
                f"will be suspended once the plan is set up and the first "
                f"payment is made. Collect their preference."
            ),
            checklist=[
                guava.Field(
                    key="plan_length_preference",
                    description="The resident's preferred payment plan length",
                    field_type="multiple_choice",
                    choices=["3 months", "6 months", "12 months"],
                    required=True,
                ),
                guava.Field(
                    key="first_payment_date",
                    description="When the resident can make the first installment payment",
                    field_type="text",
                    required=True,
                ),
            ],
        )
    elif payment_path == "hardship":
        hardship_eligible = call.get_variable("hardship_eligible")
        if hardship_eligible == "True":
            call.transfer(
                destination=HARDSHIP_LINE,
                instructions=(
                    f"Let {resident_name} know you're transferring them to the "
                    f"Hardship Assistance Program team who can help them apply. "
                    f"Reassure them that the shutoff will be paused while their "
                    f"application is being processed."
                ),
            )
        else:
            call.hangup(
                final_instructions=(
                    f"Let {resident_name} know that based on the account history, "
                    f"they may not qualify for the hardship program, but they can "
                    f"still apply. Direct them to call 1-800-555-0500 or visit a "
                    f"Springfield Municipal Utilities office to submit an application. "
                    f"Mention the payment plan option as an alternative, and politely say goodbye."
                )
            )
    else:
        # dispute
        call.transfer(
            destination=BILLING_LINE,
            instructions=(
                f"Let {resident_name} know you're connecting them with the billing "
                f"department to review and dispute the balance on their account."
            ),
        )


@agent.on_task_complete("payment_info")
def on_payment_done(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            f"Thank {call.get_variable('resident_name')} for their time. Confirm "
            f"the payment method and date they committed to. Remind them that "
            f"payment must be received before the shutoff date to avoid service "
            f"interruption. Provide the customer service number 1-800-555-0500 "
            f"for any questions, and politely say goodbye."
        )
    )


@agent.on_task_complete("payment_plan_info")
def on_plan_done(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            f"Thank {call.get_variable('resident_name')} for setting up a payment "
            f"plan. Confirm the plan length and first payment date. Let them know "
            f"a confirmation letter will be mailed and the shutoff will be suspended "
            f"once the first payment is received. Provide 1-800-555-0500 for questions, and politely say goodbye."
        )
    )


@agent.on_action_request
def on_action_request(call: guava.Call, intent_summary: str):
    return _mid_call_intent.classify(intent_summary)


@agent.on_action("do_not_contact")
def handle_dnc(call: guava.Call) -> None:
    logging.info("Resident %s requested DNC mid-call.", call.get_variable("resident_name"))
    call.hangup(
        final_instructions=(
            "Acknowledge their request. Let them know they will not be contacted "
            "again by phone. Note that important account notices will still be "
            "sent by mail, and wish them well, and politely say goodbye."
        )
    )


@agent.on_action("speak_to_billing")
def handle_transfer_request(call: guava.Call) -> None:
    call.transfer(
        destination=BILLING_LINE,
        instructions="Let them know you're connecting them with a billing representative now.",
    )


@agent.on_outbound_failed
def on_outbound_failed(event: OutboundCallFailed) -> None:
    logging.error("Outbound call failed: %s (code %d)", event.error_reason, event.error_code)


@agent.on_session_end
def on_session_end(call: guava.Call, event: BotSessionEnded) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "use_case": "utility_shutoff_warning",
        "resident_name": call.get_variable("resident_name"),
        "account_number": call.get_variable("account_number"),
        "balance": call.get_variable("balance"),
        "shutoff_date": call.get_variable("shutoff_date"),
        "dob_verified": call.get_field("dob") is not None,
        "balance_acknowledged": call.get_field("balance_acknowledged"),
        "payment_path": call.get_field("payment_path"),
        "payment_date_commitment": call.get_field("payment_date_commitment"),
        "payment_method": call.get_field("payment_method"),
        "plan_length_preference": call.get_field("plan_length_preference"),
        "first_payment_date": call.get_field("first_payment_date"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound utility shutoff warning call for Springfield Municipal Utilities"
    )
    parser.add_argument("phone", help="Resident phone number to call (E.164 format).")
    parser.add_argument("--name", required=True, help="Full name of the account holder.")
    parser.add_argument("--account-number", required=True, help="Utility account number.")
    parser.add_argument(
        "--from-number",
        default=os.environ.get("GUAVA_AGENT_NUMBER", ""),
        help="Caller ID / from number (defaults to GUAVA_AGENT_NUMBER env var).",
    )
    args = parser.parse_args()

    agent.call_phone(
        from_number=args.from_number,
        to_number=args.phone,
        variables={
            "resident_name": args.name,
            "account_number": args.account_number,
        },
    )

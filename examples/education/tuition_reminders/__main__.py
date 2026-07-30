# SDK conformance: guava-sdk 0.35.0 (2026-07-21)
import argparse
import json
import logging
import os
from datetime import datetime, timezone

import guava
from guava import logging_utils
from guava.helpers.llm import IntentRecognizer


# ---------------------------------------------------------------------------
# Mock API — simulates a student accounts backend for demo purposes
# ---------------------------------------------------------------------------

FINANCIAL_AID_LINE = "+15551000500"
BILLING_LINE = "+15551000501"

MOCK_ACCOUNTS = {
    "STU-200301": {
        "student_name": "Elena Vasquez",
        "dob": "2002-04-12",
        "term": "Fall 2026",
        "balance": "$4,850.00",
        "due_date": "August 15, 2026",
        "payment_status": "unpaid",
        "financial_aid_pending": False,
    },
    "STU-200302": {
        "student_name": "Tyler Washington",
        "dob": "2001-11-28",
        "term": "Fall 2026",
        "balance": "$2,100.00",
        "due_date": "August 15, 2026",
        "payment_status": "partial",
        "financial_aid_pending": True,
    },
    "STU-200303": {
        "student_name": "Mia Nakamura",
        "dob": "2003-08-07",
        "term": "Fall 2026",
        "balance": "$0.00",
        "due_date": "August 15, 2026",
        "payment_status": "paid",
        "financial_aid_pending": False,
    },
}


def lookup_account(student_id, dob):
    account = MOCK_ACCOUNTS.get(student_id)
    if account and account["dob"] == dob:
        return account
    return None


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

agent = guava.Agent(
    name="Pat",
    organization="Westfield University — Student Accounts",
    purpose=(
        "proactively remind students of upcoming tuition payment deadlines, "
        "verify their account balance, and assist with payment options or "
        "escalation to financial aid"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
    "speak_to_billing": "The caller wants to speak to a billing representative or live person about their account",
})


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(
        contact_full_name=call.get_variable("name"),
        voicemail_message=(
            f"Hi, this is Pat from Westfield University Student Accounts "
            f"calling for {call.get_variable('name')} regarding your student "
            f"account. Please call us back at 1-800-555-0190 at your convenience. "
            f"Thank you."
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    student_name = call.get_variable("name")

    if outcome == "available":
        call.set_task(
            "verify_identity",
            objective=(
                f"Verify the identity of {student_name} before sharing any "
                f"account details. Ask for their date of birth. Do not disclose "
                f"any balance or payment information until identity is confirmed."
            ),
            checklist=[
                guava.Say(
                    f"I'm calling regarding your student account. Before I "
                    f"share any details, I need to verify your identity with "
                    f"a quick question."
                ),
                guava.Field(
                    key="dob",
                    description="The student's date of birth for identity verification",
                    field_type="text",
                    required=True,
                ),
            ],
        )
    elif outcome == "do_not_contact":
        logging.info("Student %s requested no further contact.", student_name)
        call.hangup(
            final_instructions=(
                "Acknowledge their request. Let them know they will not be "
                "contacted again by phone and that future account notifications "
                "will be sent by email and mail, and politely say goodbye."
            )
        )
    elif outcome == "wrong_number":
        logging.info("Wrong number for %s.", student_name)
        call.hangup(final_instructions="Apologize for the mistake and wish them well, and politely say goodbye.")
    else:
        logging.info("Could not reach %s (outcome: %s).", student_name, outcome)
        call.hangup()


@agent.on_task_complete("verify_identity")
def on_identity_verified(call: guava.Call) -> None:
    student_id = call.get_variable("student_id")
    dob = call.get_field("dob")
    account = lookup_account(student_id, dob)

    if account is None:
        logging.warning("Identity verification failed for student %s.", student_id)
        call.hangup(
            final_instructions=(
                "Let them know the date of birth provided does not match our "
                "records. For security, you cannot share account details. "
                "Suggest they contact Student Accounts directly at "
                "1-800-555-0190 with their student ID handy, and politely say goodbye."
            )
        )
        return

    call.set_variable("payment_status", account["payment_status"])
    call.set_variable("balance", account["balance"])

    call.add_info("account_details", {
        "student_id": student_id,
        "term": account["term"],
        "balance": account["balance"],
        "due_date": account["due_date"],
        "payment_status": account["payment_status"],
        "financial_aid_pending": account["financial_aid_pending"],
    })

    if account["payment_status"] == "paid":
        call.set_task(
            "confirm_paid",
            objective=(
                f"Good news — {call.get_variable('name')}'s account shows a $0.00 "
                f"balance for {account['term']}. Confirm that their tuition has been "
                f"paid in full and ask if they have any questions."
            ),
            checklist=[
                guava.Field(
                    key="payment_confirmed",
                    description="Whether the student acknowledges their balance is paid in full",
                    field_type="multiple_choice",
                    choices=["yes", "has questions"],
                    required=True,
                ),
                guava.Field(
                    key="student_questions",
                    description="Any questions the student has about their account",
                    field_type="text",
                    required=False,
                ),
            ],
        )
    else:
        call.set_task(
            "present_balance",
            objective=(
                f"Present the account balance to {call.get_variable('name')}. "
                f"Their current balance is {account['balance']} due by "
                f"{account['due_date']}. Ask how they intend to handle the payment. "
                f"Do NOT offer to waive fees, adjust the balance, or make promises "
                f"about financial aid outcomes."
            ),
            checklist=[
                guava.Say(
                    f"Let {call.get_variable('name')} know that their student "
                    f"account has a balance of {account['balance']} due by "
                    f"{account['due_date']}."
                ),
                guava.Field(
                    key="payment_path",
                    description="How the student intends to handle the balance",
                    field_type="multiple_choice",
                    choices=["already_paid", "will_pay", "hardship", "dispute"],
                    required=True,
                ),
            ],
        )


@agent.on_task_complete("confirm_paid")
def on_paid_confirmed(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            f"Thank {call.get_variable('name')} for their time. Let them know "
            f"their account is in good standing. If they had questions, let them "
            f"know Student Accounts will follow up by email, and wish them a great term, and politely say goodbye."
        )
    )


@agent.on_task_complete("present_balance")
def on_balance_presented(call: guava.Call) -> None:
    payment_path = call.get_field("payment_path")
    student_name = call.get_variable("name")

    if payment_path == "already_paid":
        call.set_task(
            "verify_payment",
            objective=(
                f"{student_name} says they have already paid. Collect details so "
                f"Student Accounts can locate the payment and update the record."
            ),
            checklist=[
                guava.Field(
                    key="payment_date",
                    description="The approximate date the student made the payment",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="payment_method",
                    description="How the payment was made (e.g. online portal, check, wire transfer)",
                    field_type="text",
                    required=True,
                ),
            ],
        )
    elif payment_path == "will_pay":
        call.set_task(
            "collect_payment_plan",
            objective=(
                f"{student_name} intends to pay. Provide the online payment portal "
                f"URL (payments.westfield.edu) and collect a payment date commitment."
            ),
            checklist=[
                guava.Say(
                    f"Let {student_name} know they can make a payment online at "
                    f"payments.westfield.edu using their student ID and password."
                ),
                guava.Field(
                    key="payment_date_commitment",
                    description="The date by which the student commits to making the payment",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="payment_plan_requested",
                    description="Whether the student would like to set up a payment plan instead of paying in full",
                    field_type="multiple_choice",
                    choices=["yes", "no"],
                    required=True,
                ),
            ],
        )
    elif payment_path == "hardship":
        call.transfer(
            destination=FINANCIAL_AID_LINE,
            instructions=(
                f"The student ({student_name}) is experiencing financial hardship. "
                f"Let them know you're connecting them with the financial aid office "
                f"to discuss assistance options. Reassure them that their account "
                f"information has been saved."
            ),
        )
    else:
        call.transfer(
            destination=BILLING_LINE,
            instructions=(
                f"The student ({student_name}) is disputing their balance. Let them "
                f"know you're connecting them with a billing specialist who can review "
                f"the charges in detail."
            ),
        )


@agent.on_task_complete("verify_payment")
def on_payment_verified(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            f"Thank {call.get_variable('name')} for providing the payment details. "
            f"Let them know Student Accounts will locate the payment and update "
            f"their record. If there are any issues, someone will reach out. "
            f"Wish them a great day, and politely say goodbye."
        )
    )


@agent.on_task_complete("collect_payment_plan")
def on_payment_plan_collected(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            f"Thank {call.get_variable('name')} for their time. Confirm their "
            f"payment date commitment has been noted. Remind them the payment "
            f"portal is payments.westfield.edu, and wish them a great term, and politely say goodbye."
        )
    )


@agent.on_action_request
def on_action_request(call: guava.Call, intent_summary: str):
    return _mid_call_intent.classify(intent_summary)


@agent.on_action("do_not_contact")
def handle_dnc(call: guava.Call) -> None:
    logging.info("Student %s requested DNC mid-call.", call.get_variable("name"))
    call.hangup(
        final_instructions=(
            "Acknowledge their request. Let them know they will not be contacted "
            "again by phone and that future account updates will be sent by email, and politely say goodbye."
        )
    )


@agent.on_action("speak_to_billing")
def handle_transfer_request(call: guava.Call) -> None:
    call.transfer(
        destination=BILLING_LINE,
        instructions="Let them know you're connecting them with a billing representative now.",
    )


@agent.on_outbound_failed
def on_outbound_failed(event: guava.OutboundCallFailed) -> None:
    logging.error("Outbound call failed: %s (code %d)", event.error_reason, event.error_code)


@agent.on_session_end
def on_session_end(call: guava.Call, event: guava.BotSessionEnded) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "use_case": "tuition_reminder",
        "student_name": call.get_variable("name"),
        "student_id": call.get_variable("student_id"),
        "payment_status": call.get_variable("payment_status"),
        "balance": call.get_variable("balance"),
        "dob_verified": call.get_field("dob") is not None,
        "payment_path": call.get_field("payment_path"),
        "payment_confirmed": call.get_field("payment_confirmed"),
        "payment_date_commitment": call.get_field("payment_date_commitment"),
        "payment_plan_requested": call.get_field("payment_plan_requested"),
        "payment_date": call.get_field("payment_date"),
        "payment_method": call.get_field("payment_method"),
        "student_questions": call.get_field("student_questions"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound tuition reminder call for Westfield University Student Accounts"
    )
    parser.add_argument("phone", help="Phone number to dial")
    parser.add_argument("--name", required=True, help="Full name of the student")
    parser.add_argument(
        "--student-id",
        required=True,
        help="Student ID (try STU-200301, STU-200302, or STU-200303)",
    )
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
            "name": args.name,
            "student_id": args.student_id,
        },
    )

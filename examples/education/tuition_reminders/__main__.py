import argparse
import json
import logging
import os
from datetime import datetime

import guava
from guava import logging_utils

agent = guava.Agent(
    name="Riley",
    organization="Westfield University - Student Accounts",
    purpose=(
        "proactively remind students and guardians of upcoming tuition payment "
        "deadlines and assist with arranging payment plans if needed"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(contact_full_name=call.get_variable("name"))


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    if outcome == "unavailable":
        logging.info(
            "Could not reach %s for tuition reminder (student ID: %s).",
            call.get_variable("name"),
            call.get_variable("student_id"),
        )
        results = {
            "timestamp": datetime.now().isoformat(),
            "student_name": call.get_variable("name"),
            "student_id": call.get_variable("student_id"),
            "amount_due": call.get_variable("amount_due"),
            "due_date": call.get_variable("due_date"),
            "outcome": "recipient_unavailable",
        }
        print(json.dumps(results, indent=2))
        call.hangup(
            final_instructions=(
                "The recipient could not be reached. End the call politely."
            )
        )
    elif outcome == "available":
        call.set_task(
            "reminder",
            objective=(
                f"You are calling {call.get_variable('name')} (student ID: {call.get_variable('student_id')}) to remind them "
                f"that a tuition balance of {call.get_variable('amount_due')} is due by {call.get_variable('due_date')}. "
                "Find out how they intend to handle the payment — whether they plan to pay in full, "
                "set up a payment plan, are waiting on financial aid, or wish to dispute the balance. "
                "If they want a payment plan, confirm the arrangement. "
                "If they have a payment date commitment, capture it. "
                "Address any financial aid questions they may have."
            ),
            checklist=[
                guava.Say(
                    f"Hello {call.get_variable('name')}, this is Riley calling from Westfield University Student Accounts. "
                    f"I'm reaching out because your student account has a balance of {call.get_variable('amount_due')} "
                    f"that is due by {call.get_variable('due_date')}. I wanted to connect with you to make sure you have "
                    "everything you need and discuss any payment options that might be helpful."
                ),
                guava.Field(
                    key="payment_intention",
                    description=(
                        "How the student or guardian intends to handle the balance. "
                        "Options are: pay_now, payment_plan, financial_aid_pending, or dispute"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="payment_plan_confirmed",
                    description="Details of any payment plan arrangement discussed and confirmed with the student",
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="payment_date_commitment",
                    description="The specific date by which the student commits to making a payment or first installment",
                    field_type="date",
                    required=False,
                ),
                guava.Field(
                    key="financial_aid_questions",
                    description="Any questions or concerns the student raised about financial aid",
                    field_type="text",
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("reminder")
def on_done(call: guava.Call) -> None:
    results = {
        "timestamp": datetime.now().isoformat(),
        "student_name": call.get_variable("name"),
        "student_id": call.get_variable("student_id"),
        "amount_due": call.get_variable("amount_due"),
        "due_date": call.get_variable("due_date"),
        "fields": {
            "payment_intention": call.get_field("payment_intention"),
            "payment_plan_confirmed": call.get_field("payment_plan_confirmed"),
            "payment_date_commitment": call.get_field("payment_date_commitment"),
            "financial_aid_questions": call.get_field("financial_aid_questions"),
        },
    }
    print(json.dumps(results, indent=2))
    call.hangup(
        final_instructions=(
            f"Thank {call.get_variable('name')} for their time. Let them know that Student Accounts is available "
            "if they have further questions and provide a warm, encouraging close to the conversation."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Tuition reminder call for students approaching payment deadlines"
    )
    parser.add_argument("phone", help="Phone number to call (e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Full name of the student or guardian")
    parser.add_argument("--student-id", required=True, help="Student ID number")
    parser.add_argument(
        "--amount-due",
        required=True,
        help="Amount of tuition balance due (e.g. '$3,200.00')",
    )
    parser.add_argument(
        "--due-date",
        required=True,
        help="Payment due date (e.g. 'March 15, 2026')",
    )
    args = parser.parse_args()

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "name": args.name,
            "student_id": args.student_id,
            "amount_due": args.amount_due,
            "due_date": args.due_date,
        },
    )

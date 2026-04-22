import guava
import os
import logging
from guava import logging_utils
import json
import argparse
from datetime import datetime



class TuitionReminderController(guava.CallController):
    def __init__(self, name, student_id, amount_due, due_date):
        super().__init__()
        self.name = name
        self.student_id = student_id
        self.amount_due = amount_due
        self.due_date = due_date
        self.set_persona(
            organization_name="Westfield University - Student Accounts",
            agent_name="Riley",
            agent_purpose=(
                "proactively remind students and guardians of upcoming tuition payment "
                "deadlines and assist with arranging payment plans if needed"
            ),
        )
        self.reach_person(
            contact_full_name=self.name,
            on_success=self.begin_tuition_reminder,
            on_failure=self.recipient_unavailable,
        )

    def begin_tuition_reminder(self):
        self.set_task(
            objective=(
                f"You are calling {self.name} (student ID: {self.student_id}) to remind them "
                f"that a tuition balance of {self.amount_due} is due by {self.due_date}. "
                "Find out how they intend to handle the payment — whether they plan to pay in full, "
                "set up a payment plan, are waiting on financial aid, or wish to dispute the balance. "
                "If they want a payment plan, confirm the arrangement. "
                "If they have a payment date commitment, capture it. "
                "Address any financial aid questions they may have."
            ),
            checklist=[
                guava.Say(
                    f"Hello {self.name}, this is Riley calling from Westfield University Student Accounts. "
                    f"I'm reaching out because your student account has a balance of {self.amount_due} "
                    f"that is due by {self.due_date}. I wanted to connect with you to make sure you have "
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
            on_complete=self.save_results,
        )

    def save_results(self):
        results = {
            "timestamp": datetime.now().isoformat(),
            "student_name": self.name,
            "student_id": self.student_id,
            "amount_due": self.amount_due,
            "due_date": self.due_date,
            "fields": {
                "payment_intention": self.get_field("payment_intention"),
                "payment_plan_confirmed": self.get_field("payment_plan_confirmed"),
                "payment_date_commitment": self.get_field("payment_date_commitment"),
                "financial_aid_questions": self.get_field("financial_aid_questions"),
            },
        }
        print(json.dumps(results, indent=2))
        self.hangup(
            final_instructions=(
                f"Thank {self.name} for their time. Let them know that Student Accounts is available "
                "if they have further questions and provide a warm, encouraging close to the conversation."
            )
        )

    def recipient_unavailable(self):
        logging.info(
            "Could not reach %s for tuition reminder (student ID: %s).",
            self.name,
            self.student_id,
        )
        results = {
            "timestamp": datetime.now().isoformat(),
            "student_name": self.name,
            "student_id": self.student_id,
            "amount_due": self.amount_due,
            "due_date": self.due_date,
            "outcome": "recipient_unavailable",
        }
        print(json.dumps(results, indent=2))
        self.hangup(
            final_instructions=(
                "The recipient could not be reached. End the call politely."
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

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=TuitionReminderController(
            name=args.name,
            student_id=args.student_id,
            amount_due=args.amount_due,
            due_date=args.due_date,
        ),
    )

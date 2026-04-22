import guava
import os
import logging
import json
import argparse
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)


class CollectionsOutreachController(guava.CallController):
    def __init__(self, contact_name: str, balance: str, due_date: str):
        super().__init__()
        self.contact_name = contact_name
        self.balance = balance
        self.due_date = due_date

        self.set_persona(
            organization_name="First National Bank - Account Services",
            agent_name="Morgan",
            agent_purpose=(
                "to reach out regarding a past-due account balance, discuss available payment "
                "options, and collect a commitment-to-pay from the account holder"
            ),
        )

        self.reach_person(
            contact_full_name=self.contact_name,
            on_success=self.begin_collections_outreach,
            on_failure=self.recipient_unavailable,
        )

    def begin_collections_outreach(self):
        self.set_task(
            objective=(
                f"You are contacting {self.contact_name} from First National Bank - Account "
                f"Services regarding a past-due balance of {self.balance} that was due on "
                f"{self.due_date}. Your goal is to inform them of the outstanding balance in a "
                f"respectful, non-confrontational manner, present available resolution options "
                f"including full payment, a payment plan, or dispute process, and obtain a clear "
                f"commitment-to-pay with specific details. Always remain empathetic and solution-"
                f"focused. This is an early-stage outreach call — maintain a helpful, cooperative tone."
            ),
            checklist=[
                guava.Say(
                    f"Hello {self.contact_name}, this is Morgan calling from First National Bank "
                    f"Account Services. I am reaching out today regarding your account, which shows "
                    f"a balance of {self.balance} that was due on {self.due_date}. I want to help "
                    f"find a solution that works for you."
                ),
                guava.Say(
                    "We have a few options available. You can make a payment in full today, set up "
                    "a payment arrangement that fits your budget, or if you believe there is an "
                    "error on your account, we can open a dispute. What would work best for you?"
                ),
                guava.Field(
                    key="payment_intention",
                    description=(
                        "Record the account holder's stated intention for resolving the balance. "
                        "Expected values: 'pay_now' if they will pay today, 'payment_plan' if they "
                        "want to arrange installments, 'dispute' if they are contesting the balance, "
                        "or 'callback' if they need to call back at a later time."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="payment_date",
                    description=(
                        "If the account holder chose 'pay_now' or 'payment_plan', confirm the "
                        "specific date they commit to making their first or full payment. "
                        "Leave blank if they chose 'dispute' or 'callback'."
                    ),
                    field_type="date",
                    required=False,
                ),
                guava.Field(
                    key="payment_amount",
                    description=(
                        "If a payment plan was agreed upon, record the amount the account holder "
                        "has committed to paying per installment or the partial amount for their "
                        "first payment. Leave blank if paying in full or if no amount was discussed."
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="dispute_reason",
                    description=(
                        "If the account holder indicated they want to dispute the balance, record "
                        "a brief description of the reason they provided for the dispute. "
                        "Leave blank if no dispute was raised."
                    ),
                    field_type="text",
                    required=False,
                ),
            ],
            on_complete=self.save_results,
        )

    def save_results(self):
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "contact_name": self.contact_name,
            "balance": self.balance,
            "due_date": self.due_date,
            "payment_intention": self.get_field("payment_intention"),
            "payment_date": self.get_field("payment_date"),
            "payment_amount": self.get_field("payment_amount"),
            "dispute_reason": self.get_field("dispute_reason"),
        }
        print(json.dumps(results, indent=2))
        self.hangup(
            final_instructions=(
                f"Thank {self.contact_name} for speaking with you today. Summarize the agreed-upon "
                f"next step based on their payment intention: if paying now or on a plan, confirm "
                f"the date and amount; if disputing, let them know the dispute team will follow up "
                f"within 3 to 5 business days; if calling back, note the account will remain open. "
                f"Remind them that the Account Services team is available to help and close the "
                f"call courteously."
            )
        )

    def recipient_unavailable(self):
        self.hangup(
            final_instructions=(
                f"You were unable to reach {self.contact_name}. Leave a brief, professional "
                f"voicemail identifying yourself as Morgan from First National Bank Account "
                f"Services. Mention that you are calling regarding their account and that there is "
                f"an important matter they should address. Ask them to return the call at their "
                f"earliest convenience. Do not disclose the specific balance amount or account "
                f"details in the voicemail."
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Early-stage collections outreach to collect commitment-to-pay."
    )
    parser.add_argument("phone", help="The phone number to call (E.164 format, e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Full name of the account holder")
    parser.add_argument(
        "--balance",
        default="$0.00",
        help="Outstanding balance amount (default: '$0.00')",
    )
    parser.add_argument(
        "--due-date",
        default="today",
        help="The date the balance was due (default: 'today')",
    )
    args = parser.parse_args()

    controller = CollectionsOutreachController(
        contact_name=args.name,
        balance=args.balance,
        due_date=args.due_date,
    )

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=controller,
    )

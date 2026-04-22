import guava
import os
import logging
from guava import logging_utils
import argparse
import requests


ADYEN_API_KEY = os.environ["ADYEN_API_KEY"]
ADYEN_MERCHANT_ACCOUNT = os.environ["ADYEN_MERCHANT_ACCOUNT"]
RECURRING_BASE_URL = "https://pal-test.adyen.com/pal/servlet/Recurring/v68"

HEADERS = {
    "X-API-Key": ADYEN_API_KEY,
    "Content-Type": "application/json",
}


def fetch_recurring_details(shopper_reference: str) -> dict:
    """Fetch stored recurring payment details for a shopper."""
    resp = requests.post(
        f"{RECURRING_BASE_URL}/listRecurringDetails",
        headers=HEADERS,
        json={
            "merchantAccount": ADYEN_MERCHANT_ACCOUNT,
            "shopperReference": shopper_reference,
            "recurring": {
                "contract": "RECURRING",
            },
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


class SubscriptionPaymentNotificationController(guava.CallController):
    def __init__(
        self,
        customer_name: str,
        shopper_reference: str,
        plan_name: str,
        charge_amount: str,
        currency: str,
        charge_date: str,
    ):
        super().__init__()
        self.customer_name = customer_name
        self.shopper_reference = shopper_reference
        self.plan_name = plan_name
        self.charge_amount = charge_amount
        self.currency = currency
        self.charge_date = charge_date

        try:
            details = fetch_recurring_details(shopper_reference)
            stored = details.get("details", [])
            if stored:
                first = stored[0].get("RecurringDetail", {})
                card = first.get("card", {})
                last_four = card.get("number", "")
                self.payment_summary = f"card ending in {last_four}" if last_four else "payment method on file"
            else:
                self.payment_summary = "payment method on file"
            logging.info(
                "Fetched recurring details for shopper %s: %s",
                shopper_reference,
                self.payment_summary,
            )
        except Exception as e:
            logging.error("Could not fetch recurring details for %s: %s", shopper_reference, e)
            self.payment_summary = "payment method on file"

        self.set_persona(
            organization_name="Meridian Retail",
            agent_name="Sophie",
            agent_purpose="to notify customers about an upcoming subscription charge and answer their questions",
        )

        self.reach_person(
            contact_full_name=self.customer_name,
            on_success=self.begin_call,
            on_failure=self.recipient_unavailable,
        )

    def begin_call(self):
        self.set_task(
            objective=(
                f"Notify {self.customer_name} of an upcoming {self.plan_name} subscription charge of "
                f"{self.charge_amount} {self.currency} on {self.charge_date}. Confirm they are aware, "
                "answer any questions about their plan, and capture whether they want to make any changes."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.customer_name}, this is Sophie calling from Meridian Retail. "
                    f"I'm reaching out with a quick heads-up about your upcoming {self.plan_name} subscription renewal."
                ),
                guava.Field(
                    key="aware_of_charge",
                    field_type="multiple_choice",
                    description=(
                        f"Inform {self.customer_name} that a charge of {self.charge_amount} {self.currency} "
                        f"for their {self.plan_name} plan is scheduled to process on {self.charge_date} "
                        f"using their {self.payment_summary}. Ask if they were aware of this upcoming charge."
                    ),
                    choices=["yes", "no"],
                    required=True,
                ),
                guava.Field(
                    key="has_questions",
                    field_type="multiple_choice",
                    description=(
                        f"Ask {self.customer_name} if they have any questions about their {self.plan_name} "
                        "plan, what it includes, or the billing amount."
                    ),
                    choices=["yes", "no"],
                    required=True,
                ),
                guava.Field(
                    key="desired_action",
                    field_type="multiple_choice",
                    description=(
                        f"Ask {self.customer_name} if they would like to make any changes before the charge "
                        f"processes on {self.charge_date}."
                    ),
                    choices=[
                        "no changes, proceed as scheduled",
                        "I want to update my payment method",
                        "I want to upgrade or downgrade my plan",
                        "I want to cancel before the renewal",
                    ],
                    required=True,
                ),
            ],
            on_complete=self.handle_outcome,
        )

    def handle_outcome(self):
        aware = self.get_field("aware_of_charge")
        has_questions = self.get_field("has_questions")
        action = self.get_field("desired_action")

        logging.info(
            "Subscription notification outcome for %s (shopper: %s): aware=%s, questions=%s, action=%s",
            self.customer_name,
            self.shopper_reference,
            aware,
            has_questions,
            action,
        )

        if action == "no changes, proceed as scheduled":
            self.hangup(
                final_instructions=(
                    f"Thank {self.customer_name} for confirming. Let them know their {self.plan_name} "
                    f"subscription will renew on {self.charge_date} as planned, and they will receive an "
                    "email receipt once the payment processes. Wish them a great day and thank them "
                    "for being a valued Meridian Retail customer."
                )
            )
        elif action == "I want to update my payment method":
            self.hangup(
                final_instructions=(
                    f"Let {self.customer_name} know they can update their payment method at any time by "
                    "visiting meridianretail.com/account/billing and signing in. Changes made before "
                    f"{self.charge_date} will apply to this renewal. Offer our support line at "
                    "1-800-555-0147 if they need assistance. Thank them."
                )
            )
        elif action == "I want to upgrade or downgrade my plan":
            self.hangup(
                final_instructions=(
                    f"Tell {self.customer_name} that plan changes can be made at meridianretail.com/account/plan. "
                    "If they change their plan before the renewal date, the new pricing will apply to this billing cycle. "
                    "Let them know our team is also available at 1-800-555-0147 to walk them through options. "
                    "Thank them for reaching out."
                )
            )
        elif action == "I want to cancel before the renewal":
            self.hangup(
                final_instructions=(
                    f"Acknowledge {self.customer_name}'s request to cancel before the renewal on {self.charge_date}. "
                    "Let them know they can cancel at meridianretail.com/account/cancel, or they can speak with our "
                    "retention team at 1-800-555-0147 who may be able to offer a pause or discount. "
                    "Assure them that if they cancel before the renewal date, they will not be charged. "
                    "Thank them for being a Meridian Retail customer."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    f"Thank {self.customer_name} for their time. Let them know our team is always available "
                    "at meridianretail.com/support or 1-800-555-0147 if they have any questions. "
                    "Wish them a great day."
                )
            )

    def recipient_unavailable(self):
        self.hangup(
            final_instructions=(
                f"Leave a brief, professional voicemail for {self.customer_name}. "
                f"Mention that this is Sophie from Meridian Retail calling about their upcoming "
                f"{self.plan_name} subscription renewal of {self.charge_amount} {self.currency} "
                f"scheduled for {self.charge_date}. Ask them to visit meridianretail.com/account "
                "or call 1-800-555-0147 if they have any questions or wish to make changes. "
                "Keep the message friendly and under 30 seconds."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Proactively notify a customer about an upcoming subscription renewal charge."
    )
    parser.add_argument("phone", help="Customer phone number in E.164 format (e.g. +12125550100)")
    parser.add_argument("--name", required=True, help="Customer full name")
    parser.add_argument("--shopper-reference", required=True, help="Adyen shopper reference ID")
    parser.add_argument("--plan", required=True, help="Subscription plan name (e.g. 'Pro Annual')")
    parser.add_argument("--amount", required=True, help="Upcoming charge amount (e.g. 299.00)")
    parser.add_argument("--currency", default="USD", help="Currency code (default: USD)")
    parser.add_argument("--charge-date", required=True, help="Charge date (e.g. 'April 15th')")
    args = parser.parse_args()

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=SubscriptionPaymentNotificationController(
            customer_name=args.name,
            shopper_reference=args.shopper_reference,
            plan_name=args.plan,
            charge_amount=args.amount,
            currency=args.currency,
            charge_date=args.charge_date,
        ),
    )

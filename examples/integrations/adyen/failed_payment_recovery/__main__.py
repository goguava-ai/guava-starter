import guava
import os
import logging
from guava import logging_utils
import argparse
import requests


ADYEN_API_KEY = os.environ["ADYEN_API_KEY"]
ADYEN_MERCHANT_ACCOUNT = os.environ["ADYEN_MERCHANT_ACCOUNT"]
RECURRING_BASE_URL = "https://pal-test.adyen.com/pal/servlet/Recurring/v68"
BASE_URL = "https://checkout-test.adyen.com/v71"

HEADERS = {
    "X-API-Key": ADYEN_API_KEY,
    "Content-Type": "application/json",
}


def fetch_stored_payment_methods(shopper_reference: str) -> list:
    """Retrieve stored payment methods for a shopper from Adyen Recurring API."""
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
    data = resp.json()
    return data.get("details", [])


class FailedPaymentRecoveryController(guava.CallController):
    def __init__(self, customer_name: str, shopper_reference: str, failed_amount: str, currency: str):
        super().__init__()
        self.customer_name = customer_name
        self.shopper_reference = shopper_reference
        self.failed_amount = failed_amount
        self.currency = currency

        try:
            stored_methods = fetch_stored_payment_methods(shopper_reference)
            self.has_stored_methods = len(stored_methods) > 0
            self.stored_method_count = len(stored_methods)
            logging.info(
                "Found %d stored payment method(s) for shopper %s",
                self.stored_method_count,
                shopper_reference,
            )
        except Exception as e:
            logging.error("Failed to fetch stored payment methods: %s", e)
            self.has_stored_methods = False
            self.stored_method_count = 0

        self.set_persona(
            organization_name="Northgate Commerce",
            agent_name="Clara",
            agent_purpose="to reach customers whose recent payment was declined and help them recover it",
        )

        self.reach_person(
            contact_full_name=self.customer_name,
            on_success=self.begin_call,
            on_failure=self.recipient_unavailable,
        )

    def begin_call(self):
        stored_methods_context = (
            f"We show {self.stored_method_count} saved payment method(s) on file for their account."
            if self.has_stored_methods
            else "We do not currently show any saved payment methods on file for their account."
        )

        self.set_task(
            objective=(
                f"Inform {self.customer_name} that a recent payment of {self.failed_amount} {self.currency} "
                "was declined, understand if they can provide or update a payment method, and guide them "
                "to resolve the outstanding balance via northgatecommerce.com/billing."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.customer_name}, this is Clara calling from Northgate Commerce. "
                    "I'm reaching out because a recent payment on your account was unfortunately declined, "
                    "and I'd like to help you resolve it quickly."
                ),
                guava.Field(
                    key="aware_of_decline",
                    field_type="multiple_choice",
                    description=(
                        f"Ask {self.customer_name} whether they were aware that their recent payment "
                        f"of {self.failed_amount} {self.currency} was declined."
                    ),
                    choices=["yes", "no"],
                    required=True,
                ),
                guava.Field(
                    key="has_alternative_method",
                    field_type="multiple_choice",
                    description=(
                        f"Explain that {stored_methods_context} "
                        f"Ask {self.customer_name} if they have an alternative payment method they would "
                        "like to use, or if they would like to update their saved payment details online."
                    ),
                    choices=[
                        "yes, I will update my payment method online",
                        "yes, I would like to use a different card",
                        "no, I need more time",
                        "I want to cancel my account",
                    ],
                    required=True,
                ),
            ],
            on_complete=self.handle_outcome,
        )

    def handle_outcome(self):
        aware = self.get_field("aware_of_decline")
        resolution = self.get_field("has_alternative_method")

        logging.info(
            "Failed payment recovery outcome for %s (shopper: %s): aware=%s, resolution=%s",
            self.customer_name,
            self.shopper_reference,
            aware,
            resolution,
        )

        if resolution == "yes, I will update my payment method online":
            self.hangup(
                final_instructions=(
                    f"Thank {self.customer_name} and let them know they can update their payment method "
                    "at northgatecommerce.com/billing by signing in with their account email. "
                    "Once updated, the outstanding payment will be retried automatically within 24 hours. "
                    "Wish them a great day."
                )
            )
        elif resolution == "yes, I would like to use a different card":
            self.hangup(
                final_instructions=(
                    f"Tell {self.customer_name} that to update their card details securely, they will need "
                    "to log in to northgatecommerce.com/billing or contact our support team via live chat. "
                    "We are not able to collect card numbers over the phone for their security. "
                    "Assure them the process takes less than two minutes online. Thank them."
                )
            )
        elif resolution == "no, I need more time":
            self.hangup(
                final_instructions=(
                    f"Acknowledge that {self.customer_name} needs more time. Let them know their account "
                    "will remain active for the next 7 days while the payment is outstanding, and our team "
                    "will follow up by email. Encourage them to update their payment at "
                    "northgatecommerce.com/billing when they are ready. Thank them for their time."
                )
            )
        elif resolution == "I want to cancel my account":
            self.hangup(
                final_instructions=(
                    f"Acknowledge {self.customer_name}'s request to cancel. Let them know that account "
                    "cancellations must be handled by our customer success team, who can also explore "
                    "options like pausing their account. Provide the contact: 1-800-555-0192 or "
                    "support@northgatecommerce.com. Thank them for being a customer."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    f"Thank {self.customer_name} for their time. Let them know our team will follow up "
                    "by email with instructions to resolve the outstanding payment. Wish them a good day."
                )
            )

    def recipient_unavailable(self):
        self.hangup(
            final_instructions=(
                f"Leave a brief, professional voicemail for {self.customer_name}. "
                "Mention that this is Clara from Northgate Commerce calling about an important "
                "update regarding their account, and ask them to call back at 1-800-555-0192 "
                "or visit northgatecommerce.com/billing. Keep the message under 30 seconds."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(description="Call customers to recover a failed payment.")
    parser.add_argument("phone", help="Customer phone number in E.164 format (e.g. +12125550100)")
    parser.add_argument("--name", required=True, help="Customer full name")
    parser.add_argument("--shopper-reference", required=True, help="Adyen shopper reference ID")
    parser.add_argument("--amount", required=True, help="Failed payment amount (e.g. 89.99)")
    parser.add_argument("--currency", default="USD", help="Currency code (default: USD)")
    args = parser.parse_args()

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=FailedPaymentRecoveryController(
            customer_name=args.name,
            shopper_reference=args.shopper_reference,
            failed_amount=args.amount,
            currency=args.currency,
        ),
    )

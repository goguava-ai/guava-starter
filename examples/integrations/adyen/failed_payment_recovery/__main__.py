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


agent = guava.Agent(
    name="Clara",
    organization="Northgate Commerce",
    purpose="to reach customers whose recent payment was declined and help them recover it",
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(contact_full_name=call.get_variable("customer_name"))


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    customer_name = call.get_variable("customer_name")
    shopper_reference = call.get_variable("shopper_reference")
    failed_amount = call.get_variable("failed_amount")
    currency = call.get_variable("currency")

    if outcome == "unavailable":
        call.hangup(
            final_instructions=(
                f"Leave a brief, professional voicemail for {customer_name}. "
                "Mention that this is Clara from Northgate Commerce calling about an important "
                "update regarding their account, and ask them to call back at 1-800-555-0192 "
                "or visit northgatecommerce.com/billing. Keep the message under 30 seconds."
            )
        )
    elif outcome == "available":
        has_stored_methods = False
        stored_method_count = 0
        try:
            stored_methods = fetch_stored_payment_methods(shopper_reference)
            has_stored_methods = len(stored_methods) > 0
            stored_method_count = len(stored_methods)
            logging.info(
                "Found %d stored payment method(s) for shopper %s",
                stored_method_count,
                shopper_reference,
            )
        except Exception as e:
            logging.error("Failed to fetch stored payment methods: %s", e)

        stored_methods_context = (
            f"We show {stored_method_count} saved payment method(s) on file for their account."
            if has_stored_methods
            else "We do not currently show any saved payment methods on file for their account."
        )

        call.set_task(
            "payment_recovery",
            objective=(
                f"Inform {customer_name} that a recent payment of {failed_amount} {currency} "
                "was declined, understand if they can provide or update a payment method, and guide them "
                "to resolve the outstanding balance via northgatecommerce.com/billing."
            ),
            checklist=[
                guava.Say(
                    f"Hi {customer_name}, this is Clara calling from Northgate Commerce. "
                    "I'm reaching out because a recent payment on your account was unfortunately declined, "
                    "and I'd like to help you resolve it quickly."
                ),
                guava.Field(
                    key="aware_of_decline",
                    field_type="multiple_choice",
                    description=(
                        f"Ask {customer_name} whether they were aware that their recent payment "
                        f"of {failed_amount} {currency} was declined."
                    ),
                    choices=["yes", "no"],
                    required=True,
                ),
                guava.Field(
                    key="has_alternative_method",
                    field_type="multiple_choice",
                    description=(
                        f"Explain that {stored_methods_context} "
                        f"Ask {customer_name} if they have an alternative payment method they would "
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
        )


@agent.on_task_complete("payment_recovery")
def handle_outcome(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    shopper_reference = call.get_variable("shopper_reference")
    aware = call.get_field("aware_of_decline")
    resolution = call.get_field("has_alternative_method")

    logging.info(
        "Failed payment recovery outcome for %s (shopper: %s): aware=%s, resolution=%s",
        customer_name,
        shopper_reference,
        aware,
        resolution,
    )

    if resolution == "yes, I will update my payment method online":
        call.hangup(
            final_instructions=(
                f"Thank {customer_name} and let them know they can update their payment method "
                "at northgatecommerce.com/billing by signing in with their account email. "
                "Once updated, the outstanding payment will be retried automatically within 24 hours. "
                "Wish them a great day."
            )
        )
    elif resolution == "yes, I would like to use a different card":
        call.hangup(
            final_instructions=(
                f"Tell {customer_name} that to update their card details securely, they will need "
                "to log in to northgatecommerce.com/billing or contact our support team via live chat. "
                "We are not able to collect card numbers over the phone for their security. "
                "Assure them the process takes less than two minutes online. Thank them."
            )
        )
    elif resolution == "no, I need more time":
        call.hangup(
            final_instructions=(
                f"Acknowledge that {customer_name} needs more time. Let them know their account "
                "will remain active for the next 7 days while the payment is outstanding, and our team "
                "will follow up by email. Encourage them to update their payment at "
                "northgatecommerce.com/billing when they are ready. Thank them for their time."
            )
        )
    elif resolution == "I want to cancel my account":
        call.hangup(
            final_instructions=(
                f"Acknowledge {customer_name}'s request to cancel. Let them know that account "
                "cancellations must be handled by our customer success team, who can also explore "
                "options like pausing their account. Provide the contact: 1-800-555-0192 or "
                "support@northgatecommerce.com. Thank them for being a customer."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {customer_name} for their time. Let them know our team will follow up "
                "by email with instructions to resolve the outstanding payment. Wish them a good day."
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

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "customer_name": args.name,
            "shopper_reference": args.shopper_reference,
            "failed_amount": args.amount,
            "currency": args.currency,
        },
    )

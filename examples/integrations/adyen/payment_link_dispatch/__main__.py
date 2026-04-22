import guava
import os
import logging
from guava import logging_utils
import argparse
import requests
from datetime import datetime, timezone, timedelta


CHECKOUT_BASE_URL = os.environ.get("ADYEN_CHECKOUT_URL", "https://checkout-test.adyen.com/v71")
MERCHANT_ACCOUNT = os.environ["ADYEN_MERCHANT_ACCOUNT"]
API_KEY = os.environ["ADYEN_API_KEY"]

HEADERS = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json",
}


def create_payment_link(
    amount_str: str,
    currency: str,
    description: str,
    reference: str,
) -> dict:
    """Create an Adyen payment link and return the full response dict."""
    try:
        amount_cents = int(round(float(amount_str.replace("$", "").replace(",", "").strip()) * 100))
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"Could not parse amount '{amount_str}': {exc}") from exc

    expires_at = (datetime.now(timezone.utc) + timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S+00:00")

    payload = {
        "merchantAccount": MERCHANT_ACCOUNT,
        "amount": {
            "value": amount_cents,
            "currency": currency.upper(),
        },
        "reference": reference,
        "description": description,
        "expiresAt": expires_at,
        "returnUrl": "https://www.meridiancommerce.com/payment/thank-you",
    }

    logging.info("Creating Adyen payment link for reference=%s amount_cents=%d", reference, amount_cents)
    response = requests.post(
        f"{CHECKOUT_BASE_URL}/paymentLinks",
        json=payload,
        headers=HEADERS,
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


class PaymentLinkDispatchController(guava.CallController):
    def __init__(
        self,
        customer_name: str,
        amount: str,
        currency: str,
        description: str,
        reference: str,
    ):
        super().__init__()

        self.customer_name = customer_name
        self.amount = amount
        self.currency = currency
        self.description = description
        self.reference = reference
        self.payment_link = None
        self.link_creation_error = False

        self.set_persona(
            organization_name="Meridian Commerce",
            agent_name="Casey",
            agent_purpose=(
                "to help Meridian Commerce customers resolve outstanding balances "
                "and provide secure payment links"
            ),
        )

        # Create the payment link before reaching the customer so it is ready when they answer.
        try:
            self.payment_link = create_payment_link(
                amount_str=amount,
                currency=currency,
                description=description,
                reference=reference,
            )
            logging.info("Payment link created: %s", self.payment_link.get("url"))
        except (requests.RequestException, ValueError) as exc:
            logging.error("Failed to create payment link before call: %s", exc)
            self.link_creation_error = True

        self.reach_person(
            contact_full_name=customer_name,
            on_success=self.present_payment_link,
            on_failure=self.leave_voicemail,
        )

    def present_payment_link(self):
        self.set_task(
            objective=(
                f"Inform {self.customer_name} about their outstanding balance of {self.amount} "
                f"for '{self.description}' and find out how they'd like to proceed."
            ),
            checklist=[
                guava.Say(
                    f"Hi, may I speak with {self.customer_name}? "
                    f"This is Casey calling from Meridian Commerce. "
                    f"I'm reaching out regarding an outstanding balance of {self.amount} "
                    f"on your account for {self.description}. "
                    "I have a secure payment link ready for you and just wanted to go over your options."
                ),
                guava.Field(
                    key="ready_to_pay",
                    field_type="multiple_choice",
                    description=(
                        "Ask the customer how they'd like to proceed with the outstanding balance. "
                        "Would they like to pay now, handle it later, or do they have a concern about the charge?"
                    ),
                    choices=[
                        "yes",
                        "not right now",
                        "want to dispute",
                    ],
                    required=True,
                ),
            ],
            on_complete=self.handle_response,
        )

    def handle_response(self):
        ready_to_pay = self.fields.get("ready_to_pay", "").lower()

        if "yes" in ready_to_pay:
            if self.payment_link and not self.link_creation_error:
                link_url = self.payment_link.get("url", "unavailable")
                expires_at = self.payment_link.get("expiresAt", "within 24 hours")
                logging.info("Dispatching payment link to customer: %s", link_url)
                self.hangup(
                    final_instructions=(
                        f"Read the customer their secure payment link: {link_url} "
                        f"Let them know the link is valid for 24 hours (expires at {expires_at}) "
                        "and they can use any major credit or debit card. "
                        "Once payment is complete they will receive an email confirmation. "
                        "Thank them for their time and wish them a great day."
                    )
                )
            else:
                self.hangup(
                    final_instructions=(
                        "Apologize to the customer and let them know there was a technical issue "
                        "generating their payment link at this moment. Assure them that our billing "
                        "team will email them a working payment link within the next 30 minutes. "
                        "Thank them for their patience."
                    )
                )

        elif "not right now" in ready_to_pay:
            logging.info("Customer deferred payment. Reference=%s", self.reference)
            self.hangup(
                final_instructions=(
                    "Thank the customer for letting us know. Let them know a secure payment link "
                    "will be sent to their email address on file and will remain active for 24 hours. "
                    "If they need to arrange a different payment method or have questions, "
                    "they can call Meridian Commerce at any time. "
                    "Wish them a great day."
                )
            )

        else:
            # "want to dispute"
            logging.info("Customer wants to dispute. Reference=%s", self.reference)
            self.hangup(
                final_instructions=(
                    "Acknowledge the customer's concern and let them know you completely understand. "
                    "Assure them that you are escalating this to the Meridian Commerce billing team "
                    "who will review their account and reach out within one business day. "
                    "No payment will be expected while the dispute is under review. "
                    "Thank them for bringing this to our attention."
                )
            )

    def leave_voicemail(self):
        self.hangup(
            final_instructions=(
                f"Leave a voicemail for {self.customer_name}. Say: "
                f"'Hi, this is Casey calling from Meridian Commerce. I'm calling regarding an "
                f"outstanding balance of {self.amount} on your account for {self.description}. "
                "We'll be sending a secure payment link to your email address on file — "
                "please keep an eye out for it as it will expire within 24 hours. "
                "If you have any questions or would like to discuss your account, "
                "please don't hesitate to give us a call back. Thank you and have a great day.'"
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound payment link dispatch call via Meridian Commerce / Adyen."
    )
    parser.add_argument("phone", help="Customer phone number to call (E.164 format, e.g. +12125550100)")
    parser.add_argument("--name", required=True, help="Customer's full name")
    parser.add_argument("--amount", required=True, help="Amount owed, e.g. '149.99' or '$149.99'")
    parser.add_argument("--currency", default="USD", help="ISO 4217 currency code (default: USD)")
    parser.add_argument("--description", required=True, help="Description of the charge or invoice")
    parser.add_argument("--reference", required=True, help="Unique order or invoice reference")
    args = parser.parse_args()

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=PaymentLinkDispatchController(
            customer_name=args.name,
            amount=args.amount,
            currency=args.currency,
            description=args.description,
            reference=args.reference,
        ),
    )

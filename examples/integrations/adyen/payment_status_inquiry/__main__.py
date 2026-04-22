import guava
import os
import logging
from guava import logging_utils
import requests


CHECKOUT_BASE_URL = os.environ.get("ADYEN_CHECKOUT_URL", "https://checkout-test.adyen.com/v71")
MERCHANT_ACCOUNT = os.environ["ADYEN_MERCHANT_ACCOUNT"]
API_KEY = os.environ["ADYEN_API_KEY"]

HEADERS = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json",
}

# Human-readable status descriptions for payment link states
LINK_STATUS_MESSAGES = {
    "paid": (
        "their payment link has been successfully paid and the transaction is complete. "
        "They should have received a payment confirmation email."
    ),
    "active": (
        "their payment link is still active and has not been used yet. "
        "They can still complete the payment using the link that was sent to them."
    ),
    "expired": (
        "their payment link has expired and can no longer be used. "
        "They should contact Meridian Commerce to request a new payment link."
    ),
}


class PaymentStatusController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Meridian Commerce",
            agent_name="Riley",
            agent_purpose=(
                "to help Meridian Commerce customers check the status of their payments, "
                "refunds, and payment links"
            ),
        )

        self.set_task(
            objective=(
                "Identify what the customer needs help with — whether they want to check if a "
                "payment went through, check a refund status, or check the status of a payment link — "
                "and provide them with the most accurate and helpful information available."
            ),
            checklist=[
                guava.Say(
                    "Thank you for calling Meridian Commerce. I'm Riley, and I can help you check "
                    "the status of a payment, refund, or payment link. Let me grab a couple of "
                    "details first."
                ),
                guava.Field(
                    key="email",
                    field_type="text",
                    description="Ask for the customer's email address to help locate their account.",
                    required=True,
                ),
                guava.Field(
                    key="payment_reference",
                    field_type="text",
                    description=(
                        "Ask for their payment or order reference number. "
                        "This is typically found on their receipt or confirmation email."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="inquiry_type",
                    field_type="multiple_choice",
                    description="Ask what they would like to check the status of.",
                    choices=[
                        "check if payment went through",
                        "check refund status",
                        "check payment link status",
                    ],
                    required=True,
                ),
            ],
            on_complete=self.handle_inquiry,
        )

        self.accept_call()

    def handle_inquiry(self):
        email = self.fields.get("email", "")
        payment_reference = self.fields.get("payment_reference", "").strip()
        inquiry_type = self.fields.get("inquiry_type", "").lower()

        logging.info(
            "Status inquiry: email=%s reference=%s type=%s",
            email,
            payment_reference,
            inquiry_type,
        )

        if "payment link" in inquiry_type:
            self._handle_payment_link_inquiry(payment_reference)
        elif "refund" in inquiry_type:
            self._handle_refund_inquiry(payment_reference, email)
        else:
            # "check if payment went through"
            self._handle_payment_inquiry(payment_reference, email)

    def _handle_payment_link_inquiry(self, payment_reference: str):
        """
        Look up a payment link by ID. Adyen payment link IDs start with 'PL'.
        If the reference provided looks like a link ID, query it directly.
        Otherwise, prompt for the link ID via an additional collection step.
        """
        link_id = payment_reference.strip()

        # If it doesn't look like a payment link ID, collect the specific link ID
        if not link_id.upper().startswith("PL"):
            self.set_task(
                objective="Collect the payment link ID so we can look up the exact status.",
                checklist=[
                    guava.Say(
                        "To check your payment link status, I'll need the payment link ID. "
                        "It starts with the letters 'PL' followed by a mix of letters and numbers, "
                        "and you can find it in the payment email we sent you."
                    ),
                    guava.Field(
                        key="link_id",
                        field_type="text",
                        description=(
                            "Ask the customer for their payment link ID. "
                            "It starts with 'PL' followed by letters and numbers."
                        ),
                        required=True,
                    ),
                ],
                on_complete=self._lookup_link_by_id_field,
            )
            return

        self._fetch_and_report_link_status(link_id)

    def _lookup_link_by_id_field(self):
        link_id = self.fields.get("link_id", "").strip()
        self._fetch_and_report_link_status(link_id)

    def _fetch_and_report_link_status(self, link_id: str):
        logging.info("Fetching payment link status for link_id=%s", link_id)

        try:
            response = requests.get(
                f"{CHECKOUT_BASE_URL}/paymentLinks/{link_id}",
                headers=HEADERS,
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()

            status = data.get("status", "unknown").lower()
            amount_info = data.get("amount", {})
            amount_value = amount_info.get("value", 0)
            amount_currency = amount_info.get("currency", "USD")
            amount_display = f"{amount_currency} {amount_value / 100:.2f}"

            status_message = LINK_STATUS_MESSAGES.get(
                status,
                f"in an unknown state ('{status}'). Our team will follow up by email with more details.",
            )

            self.hangup(
                final_instructions=(
                    f"Let the customer know that we found their payment link for {amount_display}. "
                    f"The current status is: {status_message} "
                    "Thank them for calling Meridian Commerce and wish them a great day."
                )
            )

        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                logging.warning("Payment link not found: %s", link_id)
                self.hangup(
                    final_instructions=(
                        "Let the customer know we were unable to find a payment link with that ID. "
                        "Advise them to double-check the ID in their email — it should start with 'PL'. "
                        "If they still can't locate it, our billing team can look it up using their email "
                        "address and they can reach us during business hours. "
                        "Thank them for calling."
                    )
                )
            else:
                logging.error("Adyen API error fetching payment link: %s", exc)
                self.hangup(
                    final_instructions=(
                        "Apologize and let the customer know we experienced a temporary issue looking up "
                        "their payment link. Our team will follow up by email within one business day "
                        "with the status. Thank them for their patience."
                    )
                )

        except requests.RequestException as exc:
            logging.error("Network error fetching payment link: %s", exc)
            self.hangup(
                final_instructions=(
                    "Let the customer know we're experiencing a brief system issue and couldn't retrieve "
                    "their payment link status right now. Ask them to try again in a few minutes or "
                    "call back during business hours. Thank them for their patience."
                )
            )

    def _handle_refund_inquiry(self, payment_reference: str, email: str):
        """
        Adyen refund status is communicated via webhooks (REFUND, REFUND_FAILED events).
        There is no polling endpoint for refund status by PSP reference via the Checkout REST API.
        Provide the customer with an accurate explanation and set expectations.
        """
        logging.info(
            "Refund status inquiry for reference=%s email=%s", payment_reference, email
        )
        self.hangup(
            final_instructions=(
                f"Let the customer know that refund status for reference {payment_reference} "
                "is processed through our payment system and updates are delivered via email notification. "
                "Refunds typically take 3 to 5 business days to appear on their statement depending on "
                "their bank or card issuer. "
                "If they submitted the refund more than 7 business days ago and have not received it, "
                "advise them that our billing team will personally investigate and follow up by email "
                "within one business day — we have their email address on file. "
                "Thank them for calling Meridian Commerce."
            )
        )

    def _handle_payment_inquiry(self, payment_reference: str, email: str):
        """
        Adyen payment status is event-driven via webhooks (AUTHORISATION, etc.).
        There is no simple 'get payment by reference' REST endpoint on the Checkout API.
        For payment links, we can look up by link ID. For direct payments, direct the
        customer to check their confirmation email or offer a billing team follow-up.
        """
        logging.info(
            "Payment status inquiry for reference=%s email=%s", payment_reference, email
        )
        self.hangup(
            final_instructions=(
                f"Let the customer know that for payment reference {payment_reference}, "
                "successful payments generate an immediate email confirmation from Meridian Commerce. "
                "Ask them to check their inbox (and spam/junk folder) for a subject line containing "
                "'Payment Confirmation' or 'Order Confirmed'. "
                "If they completed payment via a payment link, offer to look up the link status — "
                "they just need the payment link ID from their email (it starts with 'PL'). "
                "If they still can't confirm the payment, let them know our billing team will "
                "investigate and respond by email within one business day. "
                "Thank them for calling Meridian Commerce."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=PaymentStatusController,
    )

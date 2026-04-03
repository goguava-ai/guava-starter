import guava
import os
import logging
import requests

logging.basicConfig(level=logging.INFO)

ADYEN_API_KEY = os.environ["ADYEN_API_KEY"]
ADYEN_MERCHANT_ACCOUNT = os.environ["ADYEN_MERCHANT_ACCOUNT"]
BASE_URL = "https://checkout-test.adyen.com/v71"

HEADERS = {
    "X-API-Key": ADYEN_API_KEY,
    "Content-Type": "application/json",
}


class RefundRequestController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Northgate Commerce",
            agent_name="Clara",
            agent_purpose="to help customers request refunds on their recent orders",
        )

        self.set_task(
            objective=(
                "Collect the customer's payment PSP reference, the refund amount and currency, "
                "and the reason for the refund. Then submit the refund via the Adyen Checkout API."
            ),
            checklist=[
                guava.Say(
                    "Thank you for calling Northgate Commerce. This is Clara from our customer "
                    "support team. I can help you with a refund today."
                ),
                guava.Field(
                    key="psp_reference",
                    field_type="text",
                    description=(
                        "Ask the customer for their payment PSP reference or order reference number. "
                        "It is typically a 16-character alphanumeric code found on their receipt "
                        "or order confirmation email."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="refund_amount",
                    field_type="text",
                    description=(
                        "Ask the customer for the dollar amount they would like refunded. "
                        "For example: 49.99 or 120.00."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="currency",
                    field_type="multiple_choice",
                    description="Confirm the currency for the refund.",
                    choices=["USD", "EUR", "GBP", "CAD", "AUD"],
                    required=True,
                ),
                guava.Field(
                    key="refund_reason",
                    field_type="multiple_choice",
                    description=(
                        "Ask the customer to select the reason for their refund."
                    ),
                    choices=[
                        "item not received",
                        "item damaged or defective",
                        "not as described",
                        "changed my mind",
                        "duplicate order",
                    ],
                    required=True,
                ),
            ],
            on_complete=self.handle_complete,
        )

        self.accept_call()

    def handle_complete(self):
        psp_reference = self.get_field("psp_reference").strip()
        refund_amount_str = self.get_field("refund_amount")
        currency = self.get_field("currency")
        refund_reason = self.get_field("refund_reason")

        try:
            amount_minor = int(round(float(refund_amount_str.replace("$", "").replace(",", "")) * 100))
        except (ValueError, TypeError, AttributeError):
            logging.error("Could not parse refund amount: %s", refund_amount_str)
            self.hangup(
                final_instructions=(
                    "Tell the caller that we were unable to process their refund because the "
                    "amount provided was not recognised. Ask them to call back or contact us at "
                    "support@northgatecommerce.com so a specialist can assist them. Apologize sincerely."
                )
            )
            return

        try:
            resp = requests.post(
                f"{BASE_URL}/payments/{psp_reference}/refunds",
                headers=HEADERS,
                json={
                    "merchantAccount": ADYEN_MERCHANT_ACCOUNT,
                    "amount": {
                        "currency": currency,
                        "value": amount_minor,
                    },
                    "reference": f"voice-refund-{psp_reference}",
                    "merchantRefundReason": refund_reason,
                },
                timeout=15,
            )
            resp.raise_for_status()
            result = resp.json()
            refund_psp = result.get("pspReference", "unavailable")
            logging.info("Refund submitted. Refund PSP reference: %s", refund_psp)
            success = True
        except requests.exceptions.HTTPError as e:
            logging.error(
                "Adyen refund HTTP error: %s — %s",
                e,
                e.response.text if e.response else "",
            )
            success = False
            refund_psp = None
        except Exception as e:
            logging.error("Adyen refund error: %s", e)
            success = False
            refund_psp = None

        if success:
            self.hangup(
                final_instructions=(
                    f"Tell the caller that their refund of {refund_amount_str} {currency} has been "
                    f"successfully submitted. Their refund reference number is {refund_psp}. "
                    "Refunds typically appear within 3 to 5 business days depending on their bank. "
                    "A confirmation email will be sent to the address on file. "
                    "Thank them for shopping with Northgate Commerce and wish them a great day."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    "Apologize to the caller and let them know there was an issue processing "
                    "their refund at this time. Advise them to contact our support team at "
                    "support@northgatecommerce.com or call back during business hours so a "
                    "specialist can assist them. Thank them for their patience."
                )
            )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=RefundRequestController,
    )

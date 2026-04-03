import guava
import os
import logging
import argparse
import requests

logging.basicConfig(level=logging.INFO)

CHECKOUT_BASE_URL = os.environ.get("ADYEN_CHECKOUT_URL", "https://checkout-test.adyen.com/v71")
MERCHANT_ACCOUNT = os.environ["ADYEN_MERCHANT_ACCOUNT"]
API_KEY = os.environ["ADYEN_API_KEY"]

HEADERS = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json",
}


class FraudAlertController(guava.CallController):
    def __init__(self, customer_name: str, psp_reference: str, amount: str, merchant_name: str):
        super().__init__()

        self.customer_name = customer_name
        self.psp_reference = psp_reference
        self.amount = amount
        self.merchant_name = merchant_name

        self.set_persona(
            organization_name="Meridian Commerce",
            agent_name="Morgan",
            agent_purpose=(
                "to help Meridian Commerce customers verify and, if necessary, reverse "
                "suspicious or unauthorized transactions on their account"
            ),
        )

        self.reach_person(
            contact_full_name=customer_name,
            on_success=self.verify_transaction,
            on_failure=self.leave_voicemail,
        )

    def verify_transaction(self):
        self.set_task(
            objective=(
                f"Verify whether the customer, {self.customer_name}, recognizes a recent payment of "
                f"{self.amount} at {self.merchant_name}. Collect their response and let them know "
                "what steps will be taken based on their answer."
            ),
            checklist=[
                guava.Say(
                    f"Hi, this is Morgan calling from Meridian Commerce. I'm reaching out because "
                    f"our fraud monitoring system flagged a recent payment of {self.amount} "
                    f"at {self.merchant_name} on your account, and we want to make sure it was you. "
                    "This should only take a moment."
                ),
                guava.Field(
                    key="recognized",
                    field_type="multiple_choice",
                    description=(
                        f"Ask the customer: 'Do you recognize a charge of {self.amount} "
                        f"at {self.merchant_name}?' and prompt them to select one of the options."
                    ),
                    choices=[
                        "yes, that was me",
                        "no, I did not make this purchase",
                        "I'm not sure",
                    ],
                    required=True,
                ),
            ],
            on_complete=self.handle_verification,
        )

    def handle_verification(self):
        recognized = self.fields.get("recognized", "").lower()

        if "yes" in recognized:
            logging.info(
                "Customer confirmed transaction is legitimate. pspReference=%s", self.psp_reference
            )
            self.hangup(
                final_instructions=(
                    "Thank the customer for confirming. Let them know the payment has been verified as "
                    "legitimate and no further action is needed on their part. Reassure them that "
                    "Meridian Commerce's fraud monitoring is always working to protect their account. "
                    "Wish them a great day."
                )
            )

        elif "no" in recognized or "did not" in recognized:
            logging.info(
                "Customer denied transaction. Attempting reversal. pspReference=%s", self.psp_reference
            )
            self._attempt_reversal()

        else:
            # "I'm not sure"
            logging.info(
                "Customer uncertain about transaction. pspReference=%s", self.psp_reference
            )
            self.hangup(
                final_instructions=(
                    "Let the customer know that's completely understandable. Advise them to check their "
                    "recent purchase history and any saved subscriptions. If they don't recognize it after "
                    "reviewing, they should call us back and we can investigate further or initiate a reversal. "
                    "Give them our general customer service number to call back if needed. "
                    "Thank them for their time and wish them a great day."
                )
            )

    def _attempt_reversal(self):
        payload = {
            "merchantAccount": MERCHANT_ACCOUNT,
            "reference": f"reversal-{self.psp_reference}",
        }

        try:
            response = requests.post(
                f"{CHECKOUT_BASE_URL}/payments/{self.psp_reference}/reversals",
                json=payload,
                headers=HEADERS,
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            logging.info("Reversal submitted successfully: %s", data)

            self.hangup(
                final_instructions=(
                    "Let the customer know we've immediately initiated a reversal of that payment and "
                    "they should not be charged. Advise them to: 1) Monitor their account over the next "
                    "24 to 48 hours for the reversal to appear, 2) Contact their bank or card issuer to "
                    "report the unauthorized attempt and request a new card if necessary, and "
                    "3) Review any other recent transactions for anything else they don't recognize. "
                    "Apologize for the inconvenience and thank them for helping us catch this quickly."
                )
            )

        except requests.HTTPError as exc:
            logging.error("Adyen reversal API error: %s", exc)
            self.hangup(
                final_instructions=(
                    "Apologize to the customer and let them know we were unable to automatically reverse "
                    "the payment at this time, but our fraud team has been alerted and will escalate this "
                    "immediately. Advise them to contact their bank or card issuer right away to dispute "
                    "the charge and request a new card. Give them our fraud team hotline to follow up. "
                    "Thank them for reporting this."
                )
            )

        except requests.RequestException as exc:
            logging.error("Network error during reversal: %s", exc)
            self.hangup(
                final_instructions=(
                    "Let the customer know we're experiencing a temporary system issue and could not "
                    "process the reversal automatically. Advise them to contact their bank immediately "
                    "to dispute the charge, and let them know our fraud team will follow up by email "
                    "within the hour. Thank them for their patience."
                )
            )

    def leave_voicemail(self):
        self.hangup(
            final_instructions=(
                f"Leave an urgent voicemail for {self.customer_name}. Say: "
                f"'Hi, this is Morgan calling from Meridian Commerce with an urgent security notice. "
                f"We've detected a suspicious payment of {self.amount} at {self.merchant_name} on your "
                "account and need to verify it with you as soon as possible. "
                "Please call us back immediately at your earliest convenience so we can protect your account. "
                "Thank you.'"
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Outbound fraud alert verification call via Meridian Commerce / Adyen."
    )
    parser.add_argument("phone", help="Customer phone number to call (E.164 format, e.g. +12125550100)")
    parser.add_argument("--name", required=True, help="Customer's full name")
    parser.add_argument("--psp-reference", required=True, help="Adyen PSP reference of the flagged payment")
    parser.add_argument("--amount", required=True, help="Human-readable payment amount, e.g. '$149.99'")
    parser.add_argument("--merchant", required=True, help="Merchant name where the payment occurred")
    args = parser.parse_args()

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=FraudAlertController(
            customer_name=args.name,
            psp_reference=args.psp_reference,
            amount=args.amount,
            merchant_name=args.merchant,
        ),
    )

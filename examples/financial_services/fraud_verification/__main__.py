import guava
import os
import logging
from guava import logging_utils
import json
import argparse
from datetime import datetime, timezone



class FraudVerificationController(guava.CallController):
    def __init__(self, contact_name: str, transaction: str, amount: str):
        super().__init__()
        self.contact_name = contact_name
        self.transaction = transaction
        self.amount = amount

        self.set_persona(
            organization_name="First National Bank - Fraud Prevention",
            agent_name="Alex",
            agent_purpose=(
                "to verify a potentially suspicious transaction on the cardholder's account "
                "and confirm whether the activity should be authorized or blocked"
            ),
        )

        self.reach_person(
            contact_full_name=self.contact_name,
            on_success=self.begin_fraud_verification,
            on_failure=self.recipient_unavailable,
        )

    def begin_fraud_verification(self):
        self.set_task(
            objective=(
                f"You are contacting {self.contact_name} on behalf of First National Bank's "
                f"Fraud Prevention team. A transaction has been flagged on their account: "
                f"{self.transaction} for {self.amount}. Your goal is to quickly and clearly "
                f"verify whether the cardholder recognizes this transaction, determine whether "
                f"it should be authorized or blocked, check for any additional fraud concerns, "
                f"and ask if they would like a replacement card issued. Keep the tone calm, "
                f"professional, and reassuring throughout the call."
            ),
            checklist=[
                guava.Say(
                    f"Hello {self.contact_name}, this is Alex calling from First National Bank's "
                    f"Fraud Prevention team. We have detected activity on your account that we "
                    f"want to verify with you quickly to make sure your account is secure."
                ),
                guava.Say(
                    f"We are seeing {self.transaction} for {self.amount}. "
                    f"I just need to ask you a few quick questions about this charge."
                ),
                guava.Field(
                    key="transaction_recognized",
                    description=(
                        f"Ask the cardholder whether they recognize the transaction: "
                        f"{self.transaction} for {self.amount}. "
                        f"Record their answer as 'yes' if they recognize it or 'no' if they do not."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="authorize_transaction",
                    description=(
                        "If the cardholder recognized the transaction, ask whether they would like "
                        "to authorize and allow it to process. Record 'yes' to authorize or 'no' "
                        "to block it. Leave blank if the cardholder did not recognize the transaction "
                        "and it is being treated as fraudulent."
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="additional_fraud_concerns",
                    description=(
                        "Ask the cardholder if they have noticed any other suspicious transactions "
                        "or unauthorized activity on their account. Record a summary of any concerns "
                        "they raise. Leave blank if they report no additional concerns."
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Say(
                    "For your security, I also want to ask whether you would like us to issue a "
                    "replacement card. This would cancel your current card and send a new one to "
                    "the address we have on file, typically arriving within 5 to 7 business days."
                ),
                guava.Field(
                    key="card_replacement_requested",
                    description=(
                        "Record whether the cardholder has requested a replacement card. "
                        "Expected values: 'yes' or 'no'."
                    ),
                    field_type="text",
                    required=True,
                ),
            ],
            on_complete=self.save_results,
        )

    def save_results(self):
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "contact_name": self.contact_name,
            "transaction": self.transaction,
            "amount": self.amount,
            "transaction_recognized": self.get_field("transaction_recognized"),
            "authorize_transaction": self.get_field("authorize_transaction"),
            "additional_fraud_concerns": self.get_field("additional_fraud_concerns"),
            "card_replacement_requested": self.get_field("card_replacement_requested"),
        }
        print(json.dumps(results, indent=2))
        self.hangup(
            final_instructions=(
                f"Thank {self.contact_name} for taking the time to verify their account activity. "
                f"Let them know their account security is the bank's top priority. If a replacement "
                f"card was requested, confirm it will arrive in 5 to 7 business days. If fraud was "
                f"reported, assure them that the transaction will be blocked and a fraud specialist "
                f"will follow up. Remind them to call the number on the back of their card if they "
                f"have further concerns, and close the call professionally."
            )
        )

    def recipient_unavailable(self):
        self.hangup(
            final_instructions=(
                f"You were unable to reach {self.contact_name}. Leave a brief, urgent but calm "
                f"voicemail identifying yourself as Alex from First National Bank's Fraud Prevention "
                f"team. State that there is a time-sensitive matter regarding their account and ask "
                f"them to call the fraud prevention line immediately using the number on the back of "
                f"their card or on the bank's official website. Do not disclose specific transaction "
                f"details in the voicemail."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Fraud verification call to confirm suspicious account activity."
    )
    parser.add_argument("phone", help="The phone number to call (E.164 format, e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Full name of the cardholder")
    parser.add_argument(
        "--transaction",
        default="a recent charge on your account",
        help="Description of the flagged transaction (default: 'a recent charge on your account')",
    )
    parser.add_argument(
        "--amount",
        default="$0.00",
        help="Dollar amount of the flagged transaction (default: '$0.00')",
    )
    args = parser.parse_args()

    controller = FraudVerificationController(
        contact_name=args.name,
        transaction=args.transaction,
        amount=args.amount,
    )

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=controller,
    )

import argparse
import json
import logging
import os
from datetime import datetime, timezone

import guava
from guava import logging_utils

agent = guava.Agent(
    name="Alex",
    organization="First National Bank - Fraud Prevention",
    purpose=(
        "to verify a potentially suspicious transaction on the cardholder's account "
        "and confirm whether the activity should be authorized or blocked"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(contact_full_name=call.get_variable("contact_name"))


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    if outcome == "unavailable":
        call.hangup(
            final_instructions=(
                f"You were unable to reach {call.get_variable('contact_name')}. Leave a brief, urgent but calm "
                f"voicemail identifying yourself as Alex from First National Bank's Fraud Prevention "
                f"team. State that there is a time-sensitive matter regarding their account and ask "
                f"them to call the fraud prevention line immediately using the number on the back of "
                f"their card or on the bank's official website. Do not disclose specific transaction "
                f"details in the voicemail."
            )
        )
    elif outcome == "available":
        call.set_task(
            "verification",
            objective=(
                f"You are contacting {call.get_variable('contact_name')} on behalf of First National Bank's "
                f"Fraud Prevention team. A transaction has been flagged on their account: "
                f"{call.get_variable('transaction')} for {call.get_variable('amount')}. Your goal is to quickly and clearly "
                f"verify whether the cardholder recognizes this transaction, determine whether "
                f"it should be authorized or blocked, check for any additional fraud concerns, "
                f"and ask if they would like a replacement card issued. Keep the tone calm, "
                f"professional, and reassuring throughout the call."
            ),
            checklist=[
                guava.Say(
                    f"Hello {call.get_variable('contact_name')}, this is Alex calling from First National Bank's "
                    f"Fraud Prevention team. We have detected activity on your account that we "
                    f"want to verify with you quickly to make sure your account is secure."
                ),
                guava.Say(
                    f"We are seeing {call.get_variable('transaction')} for {call.get_variable('amount')}. "
                    f"I just need to ask you a few quick questions about this charge."
                ),
                guava.Field(
                    key="transaction_recognized",
                    description=(
                        f"Ask the cardholder whether they recognize the transaction: "
                        f"{call.get_variable('transaction')} for {call.get_variable('amount')}. "
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
        )


@agent.on_task_complete("verification")
def on_done(call: guava.Call) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "contact_name": call.get_variable("contact_name"),
        "transaction": call.get_variable("transaction"),
        "amount": call.get_variable("amount"),
        "transaction_recognized": call.get_field("transaction_recognized"),
        "authorize_transaction": call.get_field("authorize_transaction"),
        "additional_fraud_concerns": call.get_field("additional_fraud_concerns"),
        "card_replacement_requested": call.get_field("card_replacement_requested"),
    }
    print(json.dumps(results, indent=2))
    call.hangup(
        final_instructions=(
            f"Thank {call.get_variable('contact_name')} for taking the time to verify their account activity. "
            f"Let them know their account security is the bank's top priority. If a replacement "
            f"card was requested, confirm it will arrive in 5 to 7 business days. If fraud was "
            f"reported, assure them that the transaction will be blocked and a fraud specialist "
            f"will follow up. Remind them to call the number on the back of their card if they "
            f"have further concerns, and close the call professionally."
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

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "contact_name": args.name,
            "transaction": args.transaction,
            "amount": args.amount,
        },
    )

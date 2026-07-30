# SDK conformance: guava-sdk 0.35.0 (2026-07-21)
import argparse
import json
import logging
import os
from datetime import datetime, timezone

import guava
from guava import logging_utils
from guava.helpers.llm import IntentRecognizer


# ---------------------------------------------------------------------------
# Mock API — simulates a fraud alert backend for demo purposes
# ---------------------------------------------------------------------------

MOCK_ALERTS = {
    "ALT-20260501": {
        "cardholder": "Maria Santos",
        "last_four_ssn": "4829",
        "dob": "1985-03-14",
        "card_last_four": "7742",
        "transaction": "Online purchase at ElectroMart.com",
        "amount": "$1,247.99",
        "transaction_date": "2026-07-24",
        "merchant_category": "electronics",
    },
    "ALT-20260502": {
        "cardholder": "David Park",
        "last_four_ssn": "7103",
        "dob": "1992-07-22",
        "card_last_four": "3381",
        "transaction": "ATM withdrawal — 1420 Maple Ave, Chicago IL",
        "amount": "$800.00",
        "transaction_date": "2026-07-25",
        "merchant_category": "atm",
    },
    "ALT-20260503": {
        "cardholder": "Rachel Kim",
        "last_four_ssn": "2256",
        "dob": "1978-11-05",
        "card_last_four": "1125",
        "transaction": "Wire transfer to overseas account",
        "amount": "$3,500.00",
        "transaction_date": "2026-07-23",
        "merchant_category": "wire_transfer",
    },
}

FRAUD_TEAM_LINE = "+15551000500"


def verify_cardholder(alert_id, last_four_ssn=None, dob=None):
    alert = MOCK_ALERTS.get(alert_id)
    if alert is None:
        return None
    if last_four_ssn and alert["last_four_ssn"] == last_four_ssn:
        return alert
    if dob and alert["dob"] == dob:
        return alert
    return None


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

agent = guava.Agent(
    name="Alex",
    organization="National Internet Bank — Fraud Prevention",
    purpose=(
        "verify a potentially fraudulent transaction with the cardholder, "
        "confirm whether the activity is authorized, and take appropriate "
        "action to protect the account"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
    "speak_to_someone": "The caller wants to speak to a fraud specialist or live person",
})


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(
        contact_full_name=call.get_variable("contact_name"),
        voicemail_message=(
            f"Hi, this is Alex from National Internet Bank's Fraud Prevention team "
            f"calling for {call.get_variable('contact_name')}. We have a time-sensitive "
            f"matter regarding your account. Please call the fraud prevention line "
            f"using the number on the back of your card as soon as possible. Thank you."
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    contact_name = call.get_variable("contact_name")

    if outcome == "available":
        call.set_task(
            "verify_identity",
            objective=(
                f"Verify the identity of {contact_name} before sharing any transaction "
                f"details. Ask for their date of birth AND the last four digits of their "
                f"Social Security number. Both are required for fraud verification. "
                f"Do NOT reveal the flagged transaction, amount, or any account details "
                f"until identity is fully confirmed. Do not provide financial advice or "
                f"make liability statements."
            ),
            checklist=[
                guava.Say(
                    "We've detected activity on your account that we need to verify "
                    "with you. For your security, I need to confirm your identity "
                    "first."
                ),
                guava.Field(
                    key="dob",
                    description="The cardholder's date of birth for identity verification",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="last_four_ssn",
                    description=(
                        "The last four digits of the cardholder's Social Security number"
                    ),
                    field_type="text",
                    required=True,
                    sensitive=True,
                ),
            ],
        )
    elif outcome == "do_not_contact":
        logging.info("Cardholder %s requested no further contact.", contact_name)
        call.hangup(
            final_instructions=(
                "Acknowledge their request. Let them know they will not be contacted "
                "again by phone. Suggest they call the fraud line using the number "
                "on the back of their card to address the alert on their account, and politely say goodbye."
            )
        )
    elif outcome == "wrong_number":
        logging.info("Wrong number for %s.", contact_name)
        call.hangup(final_instructions="Apologize for the mistake and wish them well, and politely say goodbye.")
    else:
        logging.info("Could not reach %s (outcome: %s).", contact_name, outcome)
        call.hangup()


@agent.on_task_complete("verify_identity")
def on_identity_verified(call: guava.Call) -> None:
    alert_id = call.get_variable("alert_id")
    dob = call.get_field("dob")
    last_four_ssn = call.get_field("last_four_ssn")
    alert = verify_cardholder(alert_id, last_four_ssn=last_four_ssn, dob=dob)

    if alert is None:
        logging.warning("Identity verification failed for alert %s.", alert_id)
        call.hangup(
            final_instructions=(
                "Let them know the information provided does not match our records. "
                "For security, you cannot share account details. Suggest they call "
                "the fraud prevention line using the number on the back of their card, and politely say goodbye."
            )
        )
        return

    contact_name = call.get_variable("contact_name")

    call.add_info("flagged_transaction", {
        "alert_id": alert_id,
        "transaction": alert["transaction"],
        "amount": alert["amount"],
        "transaction_date": alert["transaction_date"],
        "card_last_four": alert["card_last_four"],
    })

    call.set_task(
        "verify_transaction",
        objective=(
            f"Identity verified. Present the flagged transaction to {contact_name}: "
            f"{alert['transaction']} for {alert['amount']} on {alert['transaction_date']} "
            f"on the card ending in {alert['card_last_four']}. Determine whether they "
            f"recognize and authorize this transaction. Do NOT provide financial advice "
            f"or make any liability statements."
        ),
        checklist=[
            guava.Say(
                f"Thank you, {contact_name}. Your identity has been verified. "
                f"We flagged a transaction on your card ending in {alert['card_last_four']}: "
                f"{alert['transaction']} for {alert['amount']} on {alert['transaction_date']}."
            ),
            guava.Field(
                key="transaction_recognized",
                description="Whether the cardholder recognizes this transaction",
                field_type="multiple_choice",
                choices=["yes", "no", "not_sure"],
                required=True,
            ),
            guava.Field(
                key="additional_concerns",
                description=(
                    "Any other suspicious transactions or unauthorized activity "
                    "the cardholder has noticed. Leave blank if none."
                ),
                field_type="text",
                required=False,
            ),
        ],
    )


@agent.on_task_complete("verify_transaction")
def on_transaction_verified(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    recognized = call.get_field("transaction_recognized")

    if recognized == "yes":
        call.hangup(
            final_instructions=(
                f"Let {contact_name} know the alert has been cleared and the "
                f"transaction will process normally. Reassure them that their account "
                f"is secure. Thank them for verifying and remind them to call the "
                f"number on the back of their card if they notice anything suspicious "
                f"in the future, and politely say goodbye."
            )
        )
    elif recognized == "not_sure":
        call.transfer(
            destination=FRAUD_TEAM_LINE,
            instructions=(
                f"Let {contact_name} know you're connecting them with a fraud "
                f"specialist who can review the transaction in more detail and help "
                f"determine whether it's authorized. Reassure them that their "
                f"information has been noted."
            ),
        )
    else:
        call.transfer(
            destination=FRAUD_TEAM_LINE,
            instructions=(
                f"Let {contact_name} know the transaction will be blocked and their "
                f"card ending in the relevant digits will be frozen for protection. "
                f"You're connecting them with the fraud team to complete the process "
                f"and arrange a replacement card."
            ),
        )


@agent.on_action_request
def on_action_request(call: guava.Call, intent_summary: str):
    return _mid_call_intent.classify(intent_summary)


@agent.on_action("do_not_contact")
def handle_dnc(call: guava.Call) -> None:
    logging.info("Cardholder %s requested DNC mid-call.", call.get_variable("contact_name"))
    call.hangup(
        final_instructions=(
            "Acknowledge their request. Let them know they will not be contacted "
            "again by phone. Remind them to call the fraud line on the back of "
            "their card to address the alert, and politely say goodbye."
        )
    )


@agent.on_action("speak_to_someone")
def handle_transfer(call: guava.Call) -> None:
    call.transfer(
        destination=FRAUD_TEAM_LINE,
        instructions="Let them know you're connecting them with a fraud specialist now.",
    )


@agent.on_outbound_failed
def on_outbound_failed(event: guava.OutboundCallFailed) -> None:
    logging.error("Outbound call failed: %s (code %d)", event.error_reason, event.error_code)


@agent.on_session_end
def on_session_end(call: guava.Call, event: guava.BotSessionEnded) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "use_case": "fraud_verification",
        "contact_name": call.get_variable("contact_name"),
        "alert_id": call.get_variable("alert_id"),
        "identity_verified": (
            call.get_field("dob") is not None and call.get_field("last_four_ssn") is not None
        ),
        "transaction_recognized": call.get_field("transaction_recognized"),
        "additional_concerns": call.get_field("additional_concerns"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound fraud verification call for National Internet Bank"
    )
    parser.add_argument("phone", help="Phone number to dial")
    parser.add_argument("--name", required=True, help="Full name of the cardholder")
    parser.add_argument(
        "--alert-id",
        required=True,
        help="Fraud alert ID (try ALT-20260501, ALT-20260502, or ALT-20260503)",
    )
    parser.add_argument(
        "--from-number",
        default=os.environ.get("GUAVA_AGENT_NUMBER", ""),
        help="Caller ID / from number (defaults to GUAVA_AGENT_NUMBER env var).",
    )
    args = parser.parse_args()

    agent.call_phone(
        from_number=args.from_number,
        to_number=args.phone,
        variables={
            "contact_name": args.name,
            "alert_id": args.alert_id,
        },
    )

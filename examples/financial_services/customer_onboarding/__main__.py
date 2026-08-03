# SDK conformance: guava-sdk 0.35.0 (2026-07-21)
import argparse
import json
import logging
import os
from datetime import datetime, timezone

import guava
from guava import logging_utils
from guava.helpers.llm import IntentRecognizer
from guava.events import BotSessionEnded, OutboundCallFailed


# ---------------------------------------------------------------------------
# Mock API — simulates an account status backend for demo purposes
# ---------------------------------------------------------------------------

MOCK_ACCOUNTS = {
    "ACCT-100201": {
        "customer": "Maria Santos",
        "dob": "1985-03-14",
        "account_type": "checking",
        "status": "pending_setup",
        "branch": "Downtown",
    },
    "ACCT-100202": {
        "customer": "David Park",
        "dob": "1992-07-22",
        "account_type": "savings",
        "status": "pending_setup",
        "branch": "Westside",
    },
    "ACCT-100203": {
        "customer": "Rachel Kim",
        "dob": "1978-11-05",
        "account_type": "both",
        "status": "pending_setup",
        "branch": "Northgate",
    },
}


def lookup_account(account_number, dob):
    account = MOCK_ACCOUNTS.get(account_number)
    if account and account["dob"] == dob:
        return account
    return None


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

agent = guava.Agent(
    name="Riley",
    organization="National Internet Bank",
    purpose=(
        "welcome new customers, verify their identity, and walk them through "
        "account setup steps including disclosures, preferences, and debit card "
        "delivery confirmation"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
    "speak_to_someone": "The caller wants to speak to a live support representative or manager",
})

SUPPORT_LINE = "+15551000400"


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(
        contact_full_name=call.get_variable("contact_name"),
        voicemail_message=(
            f"Hi, this is Riley from National Internet Bank calling for "
            f"{call.get_variable('contact_name')}. We're reaching out to help you "
            f"complete your new account setup. Please call us back at 1-800-555-0160 "
            f"at your convenience. Thank you!"
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    contact_name = call.get_variable("contact_name")

    if outcome == "available":
        call.set_task(
            "verify_identity",
            objective=(
                f"Verify the identity of {contact_name} before proceeding with "
                f"account setup. Ask for their date of birth. Do not discuss account "
                f"details or proceed with setup until identity is confirmed."
            ),
            checklist=[
                guava.Say(
                    "Congratulations on opening your new account! I'm here to help "
                    "you get everything set up. Before we begin, I just need to verify "
                    "your identity with a quick question."
                ),
                guava.Field(
                    key="dob",
                    description="The customer's date of birth for identity verification",
                    field_type="text",
                    required=True,
                ),
            ],
        )
    elif outcome == "do_not_contact":
        logging.info("Customer %s requested no further contact.", contact_name)
        call.hangup(
            final_instructions=(
                "Acknowledge their request. Let them know they will not be contacted "
                "again by phone and that they can complete account setup online or at "
                "any branch location, and politely say goodbye."
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
    account_number = call.get_variable("account_number")
    dob = call.get_field("dob")
    account = lookup_account(account_number, dob)

    if account is None:
        logging.warning("Identity verification failed for account %s.", account_number)
        call.hangup(
            final_instructions=(
                "Let them know the date of birth provided does not match our records. "
                "For security, you cannot proceed with account setup. Suggest they "
                "visit a branch with their ID or call 1-800-555-0160 for assistance, and politely say goodbye."
            )
        )
        return

    contact_name = call.get_variable("contact_name")
    account_type = account["account_type"]

    call.add_info("account_details", {
        "account_number": account_number,
        "account_type": account_type,
        "branch": account["branch"],
        "status": account["status"],
    })

    if account_type == "both":
        setup_description = (
            "checking and savings accounts. We'll walk through the setup for both."
        )
    elif account_type == "savings":
        setup_description = (
            "savings account. I'll walk you through a few quick setup steps."
        )
    else:
        setup_description = (
            "checking account. I'll walk you through a few quick setup steps."
        )

    checklist_items = [
        guava.Say(
            f"Thank you, {contact_name}. Your identity has been verified. "
            f"Let's get your new {setup_description}"
        ),
        guava.Say(
            "Before we get started with your preferences, I'm required to share a "
            "few important disclosures. By opening this account, you agree to the "
            "Deposit Account Agreement and the Fee Schedule, both of which are "
            "available on our website and will be mailed to you within 7 business "
            "days. Your deposits are insured by the FDIC up to $250,000."
        ),
        guava.Field(
            key="disclosures_acknowledged",
            description=(
                "Confirm the customer has heard and acknowledged the required "
                "disclosures including the Deposit Account Agreement, Fee Schedule, "
                "and FDIC insurance information"
            ),
            field_type="text",
            required=True,
        ),
        guava.Field(
            key="paperless_statements",
            description="Whether the customer wants to enroll in paperless statements",
            field_type="multiple_choice",
            choices=["yes", "no"],
            required=True,
        ),
    ]

    if account_type in ("checking", "both"):
        checklist_items.extend([
            guava.Field(
                key="overdraft_protection",
                description="Whether the customer wants overdraft protection on their checking account",
                field_type="multiple_choice",
                choices=["yes", "no"],
                required=True,
            ),
            guava.Field(
                key="debit_card_address_confirmed",
                description=(
                    "Confirm the mailing address on file is correct for debit card "
                    "delivery. Record 'confirmed' or the corrected address."
                ),
                field_type="text",
                required=True,
            ),
        ])

    if account_type == "savings":
        checklist_items.append(
            guava.Field(
                key="auto_transfer",
                description=(
                    "Whether the customer would like to set up automatic transfers "
                    "from another account into their new savings account"
                ),
                field_type="multiple_choice",
                choices=["yes", "no", "decide_later"],
                required=True,
            ),
        )

    if account_type == "both":
        checklist_items.append(
            guava.Field(
                key="auto_transfer",
                description=(
                    "Whether the customer would like to set up automatic transfers "
                    "between their new checking and savings accounts"
                ),
                field_type="multiple_choice",
                choices=["yes", "no", "decide_later"],
                required=True,
            ),
        )

    call.set_task(
        "account_setup",
        objective=(
            f"Walk {contact_name} through their new {account_type} account setup. "
            f"Cover required disclosures, statement preferences, and account-specific "
            f"options. Be warm, clear, and patient."
        ),
        checklist=checklist_items,
    )


@agent.on_task_complete("account_setup")
def on_setup_done(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")

    call.hangup(
        final_instructions=(
            f"Congratulate {contact_name} on completing their account setup. Provide "
            f"a brief summary of their selections. Let them know their debit card "
            f"will arrive within 5 to 7 business days if applicable, and that they "
            f"can begin using online and mobile banking immediately. Share the "
            f"customer service number 1-800-555-0160 for any questions and close "
            f"the call warmly, welcoming them to National Internet Bank, and politely say goodbye."
        )
    )


@agent.on_action_request
def on_action_request(call: guava.Call, intent_summary: str):
    return _mid_call_intent.classify(intent_summary)


@agent.on_action("do_not_contact")
def handle_dnc(call: guava.Call) -> None:
    logging.info("Customer %s requested DNC mid-call.", call.get_variable("contact_name"))
    call.hangup(
        final_instructions=(
            "Acknowledge their request. Let them know they will not be contacted "
            "again by phone. They can complete setup online or at any branch, and politely say goodbye."
        )
    )


@agent.on_action("speak_to_someone")
def handle_transfer(call: guava.Call) -> None:
    call.transfer(
        destination=SUPPORT_LINE,
        instructions=(
            "Let them know you're connecting them with a support representative now. "
            "Reassure them that any information collected so far has been saved."
        ),
    )


@agent.on_outbound_failed
def on_outbound_failed(event: OutboundCallFailed) -> None:
    logging.error("Outbound call failed: %s (code %d)", event.error_reason, event.error_code)


@agent.on_session_end
def on_session_end(call: guava.Call, event: BotSessionEnded) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "use_case": "customer_onboarding",
        "contact_name": call.get_variable("contact_name"),
        "account_number": call.get_variable("account_number"),
        "identity_verified": call.get_field("dob") is not None,
        "disclosures_acknowledged": call.get_field("disclosures_acknowledged"),
        "paperless_statements": call.get_field("paperless_statements"),
        "overdraft_protection": call.get_field("overdraft_protection"),
        "debit_card_address_confirmed": call.get_field("debit_card_address_confirmed"),
        "auto_transfer": call.get_field("auto_transfer"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound new customer onboarding call for National Internet Bank"
    )
    parser.add_argument("phone", help="Phone number to dial")
    parser.add_argument("--name", required=True, help="Full name of the new customer")
    parser.add_argument(
        "--account-number",
        required=True,
        help="Account number (try ACCT-100201, ACCT-100202, or ACCT-100203)",
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
            "account_number": args.account_number,
        },
    )

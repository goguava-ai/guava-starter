# SDK conformance: guava-sdk 0.42.0 (2026-09-08)
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
# Mock API — simulates an account lookup backend for demo purposes
# ---------------------------------------------------------------------------

MOCK_ACCOUNTS = {
    "ACCT-881234": {
        "account_holder": "Maria Santos",
        "last_four_ssn": "4829",
        "dob": "1985-03-14",
        "balance": "$2,347.00",
        "due_date": "2026-06-15",
        "days_past_due": 41,
    },
    "ACCT-776543": {
        "account_holder": "David Park",
        "last_four_ssn": "7103",
        "dob": "1992-07-22",
        "balance": "$812.50",
        "due_date": "2026-07-01",
        "days_past_due": 25,
    },
    "ACCT-990087": {
        "account_holder": "Rachel Kim",
        "last_four_ssn": "2256",
        "dob": "1978-11-05",
        "balance": "$5,610.00",
        "due_date": "2026-05-20",
        "days_past_due": 67,
    },
}


def verify_account(account_number, last_four_ssn=None, dob=None):
    account = MOCK_ACCOUNTS.get(account_number)
    if account is None:
        return None
    if last_four_ssn and account["last_four_ssn"] == last_four_ssn:
        return account
    if dob and account["dob"] == dob:
        return account
    return None


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

agent = guava.Agent(
    name="Casey",
    organization="National Internet Bank — Account Services",
    purpose=(
        "reach out regarding a past-due account balance, verify the account "
        "holder's identity, discuss available payment options, and collect a "
        "commitment-to-pay in a respectful, compliant manner"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
    "hostile_or_legal": (
        "The caller is becoming hostile, threatening, using abusive language, "
        "or invoking legal representation or cease-and-desist"
    ),
})


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(
        contact_full_name=call.get_variable("contact_name"),
        voicemail_message=(
            f"Hi, this is Casey from National Internet Bank calling for "
            f"{call.get_variable('contact_name')}. We're reaching out regarding "
            f"an important matter about your account. Please call us back at "
            f"1-800-555-0150 at your convenience. Thank you."
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    contact_name = call.get_variable("contact_name")

    if outcome == "available":
        call.set_task(
            "verify_identity",
            objective=(
                f"Verify the identity of {contact_name} before discussing any "
                f"account details. Ask for the last four digits of their Social "
                f"Security number OR their date of birth. Do NOT reveal the account "
                f"balance, past-due status, or any account details until identity is "
                f"confirmed. Never make threats, provide legal interpretations, or "
                f"imply legal consequences."
            ),
            checklist=[
                guava.Say(
                    f"I'm reaching out regarding your account. Before we "
                    f"discuss any details, I need to verify your identity "
                    f"with a quick question."
                ),
                guava.Field(
                    key="last_four_ssn",
                    description=(
                        "The last four digits of the account holder's Social Security "
                        "number for identity verification"
                    ),
                    field_type="text",
                    required=False,
                    sensitive=True,
                ),
                guava.Field(
                    key="dob",
                    description=(
                        "The account holder's date of birth, as an alternative to "
                        "SSN verification"
                    ),
                    field_type="text",
                    required=False,
                ),
            ],
        )
    elif outcome == "do_not_contact":
        logging.info("Account holder %s requested no further contact.", contact_name)
        call.hangup(
            final_instructions=(
                "Acknowledge their request. Let them know they have been removed from "
                "our outreach list and will not be contacted again by phone, and politely say goodbye."
            )
        )
    elif outcome == "wrong_number":
        logging.info("Wrong number reached for %s.", contact_name)
        call.hangup(final_instructions="Apologize for the mistake and wish them well, and politely say goodbye.")
    else:
        logging.info("Could not reach %s (outcome: %s).", contact_name, outcome)
        call.hangup()


@agent.on_task_complete("verify_identity")
def on_identity_verified(call: guava.Call) -> None:
    account_number = call.get_variable("account_number")
    last_four_ssn = call.get_field("last_four_ssn")
    dob = call.get_field("dob")
    account = verify_account(account_number, last_four_ssn=last_four_ssn, dob=dob)

    if account is None:
        logging.warning("Identity verification failed for account %s.", account_number)
        call.hangup(
            final_instructions=(
                "Let them know the information provided does not match our records "
                "for this account. For security, you cannot discuss account details. "
                "Suggest they call our main line at 1-800-555-0150 with their account "
                "documents handy, and politely say goodbye."
            )
        )
        return

    contact_name = call.get_variable("contact_name")

    call.add_info("account_details", {
        "account_number": account_number,
        "balance": account["balance"],
        "due_date": account["due_date"],
        "days_past_due": account["days_past_due"],
    })

    call.set_task(
        "present_balance",
        objective=(
            f"Identity verified. Inform {contact_name} of their outstanding balance "
            f"of {account['balance']} that was due on {account['due_date']}. Present "
            f"the available resolution options: pay in full, set up a payment plan, "
            f"request hardship assistance, or dispute the balance. Remain empathetic "
            f"and solution-focused. Never make threats, never provide legal "
            f"interpretations, and never imply legal consequences of non-payment."
        ),
        checklist=[
            guava.Say(
                f"Thank you for confirming that, {contact_name}. I'm reaching out "
                f"because your account shows a balance of {account['balance']} that "
                f"was due on {account['due_date']}. I want to help find a solution "
                f"that works for you."
            ),
            guava.Say(
                "We have a few options available. You can make a payment in full, "
                "set up a payment arrangement that fits your budget, speak with a "
                "financial hardship counselor, or if you believe there is an error, "
                "we can open a dispute. What would work best for you?"
            ),
            guava.Field(
                key="payment_intention",
                description="The account holder's stated intention for resolving the balance.",
                field_type="multiple_choice",
                choices=["pay_now", "payment_plan", "hardship", "dispute"],
                required=True,
            ),
            guava.Field(
                key="payment_date",
                description=(
                    "If paying now or setting up a plan, the specific date they commit "
                    "to making their first or full payment. Leave blank for hardship or dispute."
                ),
                field_type="text",
                required=False,
            ),
            guava.Field(
                key="payment_amount",
                description=(
                    "If a payment plan was agreed upon, the amount per installment. "
                    "Leave blank if paying in full or if no amount was discussed."
                ),
                field_type="text",
                required=False,
            ),
            guava.Field(
                key="dispute_reason",
                description=(
                    "If the account holder wants to dispute the balance, a brief "
                    "description of the reason. Leave blank if no dispute was raised."
                ),
                field_type="text",
                required=False,
            ),
        ],
    )


@agent.on_task_complete("present_balance")
def on_balance_discussed(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    intention = call.get_field("payment_intention")

    if intention == "hardship":
        call.transfer(
            destination="+15551000350",
            instructions=(
                f"Let {contact_name} know you are connecting them with a financial "
                f"hardship counselor who can discuss assistance programs. Reassure them "
                f"that their information has been noted."
            ),
        )
    elif intention == "dispute":
        call.transfer(
            destination="+15551000351",
            instructions=(
                f"Let {contact_name} know you are transferring them to the billing "
                f"dispute team, who will review their concern. Let them know the dispute "
                f"reason has been recorded."
            ),
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {contact_name} for speaking with you today. Summarize the agreed-upon "
                f"next step: if paying now, confirm the date; if on a plan, confirm the "
                f"amount and schedule. Remind them they can call Account Services at "
                f"1-800-555-0150 if they need help. Close the call courteously, and politely say goodbye."
            )
        )


@agent.on_action_request
def on_action_request(call: guava.Call, intent_summary: str):
    return _mid_call_intent.classify(intent_summary)


@agent.on_action("do_not_contact")
def handle_dnc(call: guava.Call) -> None:
    logging.info("Account holder %s requested DNC mid-call.", call.get_variable("contact_name"))
    call.hangup(
        final_instructions=(
            "Acknowledge their request immediately. Let them know they have been "
            "removed from the contact list and will not be called again, and wish them well, and politely say goodbye."
        )
    )


@agent.on_action("hostile_or_legal")
def handle_hostile(call: guava.Call) -> None:
    logging.info("Hostile or legal escalation from %s.", call.get_variable("contact_name"))
    call.hangup(
        final_instructions=(
            "Remain calm and professional. Acknowledge their frustration. Let them "
            "know you understand this is a difficult situation and that their request "
            "has been noted. Let them know they can reach us in writing if they prefer. "
            "Wish them well, and politely say goodbye."
        )
    )


@agent.on_outbound_failed
def on_outbound_failed(event: OutboundCallFailed) -> None:
    logging.error("Outbound call failed: %s (code %d)", event.error_reason, event.error_code)


@agent.on_session_end
def on_session_end(call: guava.Call, event: BotSessionEnded) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "use_case": "collections_outreach",
        "contact_name": call.get_variable("contact_name"),
        "account_number": call.get_variable("account_number"),
        "identity_verified": call.get_field("last_four_ssn") is not None or call.get_field("dob") is not None,
        "payment_intention": call.get_field("payment_intention"),
        "payment_date": call.get_field("payment_date"),
        "payment_amount": call.get_field("payment_amount"),
        "dispute_reason": call.get_field("dispute_reason"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound collections outreach call for National Internet Bank"
    )
    parser.add_argument("phone", help="Phone number to dial")
    parser.add_argument("--name", required=True, help="Full name of the account holder")
    parser.add_argument(
        "--account-number",
        required=True,
        help="Account number (try ACCT-881234, ACCT-776543, or ACCT-990087)",
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

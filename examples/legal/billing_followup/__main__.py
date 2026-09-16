# SDK conformance: guava-sdk 0.44.0 (2026-09-15)
import argparse
import json
import logging
import os
from datetime import datetime, timezone

import guava
from guava import logging_utils
from guava.helpers.llm import IntentRecognizer
from guava.events import BotSessionEnded, OutboundCallFailed

agent = guava.Agent(
    name="Sage",
    organization="Hargrove & Associates Law Firm — Billing",
    purpose=(
        "follow up on an outstanding invoice, confirm its receipt, and collect "
        "the client's payment intention, commitment date, or dispute details"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
    "speak_to_someone": "The caller wants to speak to a billing manager or live person",
})


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(
        contact_full_name=call.get_variable("contact_name"),
        voicemail_message=(
            f"Hi, this is Sage from the billing department at Hargrove & Associates "
            f"calling for {call.get_variable('contact_name')}. We're following up on "
            f"a recent invoice. Please call us back at your convenience. Thank you."
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    contact_name = call.get_variable("contact_name")
    invoice_number = call.get_variable("invoice_number")
    amount_due = call.get_variable("amount_due")
    due_date = call.get_variable("due_date")

    if outcome == "available":
        call.set_task(
            "billing_followup",
            objective=(
                f"Follow up on invoice {invoice_number} in the amount of "
                f"{amount_due}, which was due on {due_date}. Confirm the client "
                f"received the invoice and determine their payment intention. "
                f"Remain courteous, professional, and non-confrontational."
            ),
            checklist=[
                guava.Say(
                    f"I'm reaching out regarding invoice {invoice_number} in the "
                    f"amount of {amount_due}, which had a due date of {due_date}. "
                    f"I wanted to follow up to check on the status of payment."
                ),
                guava.Field(
                    key="invoice_received",
                    description="Whether the client confirms they received the invoice",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="payment_intention",
                    description="The client's stated intention regarding payment",
                    field_type="multiple_choice",
                    choices=["pay_in_full", "payment_plan", "dispute"],
                    required=True,
                ),
                guava.Field(
                    key="payment_date",
                    description=(
                        "If paying, the specific date by which they commit to "
                        "submitting payment. Leave blank for disputes."
                    ),
                    field_type="text",
                    required=False,
                ),
            ],
        )
    elif outcome == "do_not_contact":
        logging.info("Client %s requested no further contact.", contact_name)
        call.hangup(
            final_instructions=(
                "Acknowledge their request. Let them know they will not be contacted "
                "again by phone and that billing correspondence will continue by mail, and politely say goodbye."
            )
        )
    elif outcome == "wrong_number":
        logging.info("Wrong number for %s.", contact_name)
        call.hangup(final_instructions="Apologize for the mistake and wish them well, and politely say goodbye.")
    else:
        logging.info("Could not reach %s (outcome: %s).", contact_name, outcome)
        call.hangup()


@agent.on_task_complete("billing_followup")
def on_followup_done(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    intention = call.get_field("payment_intention")

    if intention == "pay_in_full":
        call.hangup(
            final_instructions=(
                f"Thank {contact_name} for confirming payment. Summarize the "
                f"committed payment date. Let them know they will receive a "
                f"receipt once payment is processed, and wish them a good day, and politely say goodbye."
            )
        )
    elif intention == "dispute":
        call.set_task(
            "dispute_details",
            objective=(
                f"{contact_name} is disputing the invoice. Collect the specific "
                f"reason for the dispute and schedule a callback from the billing "
                f"team to discuss resolution."
            ),
            checklist=[
                guava.Field(
                    key="dispute_details",
                    description=(
                        "Detailed description of which line items or charges the "
                        "client is disputing and why"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="preferred_callback_time",
                    description=(
                        "When the client would like a callback from the billing "
                        "team to discuss the dispute"
                    ),
                    field_type="text",
                    required=True,
                ),
            ],
        )
    else:
        call.set_task(
            "payment_plan_details",
            objective=(
                f"{contact_name} has requested a payment plan. Explain that "
                f"the billing team will prepare plan options and schedule a callback."
            ),
            checklist=[
                guava.Field(
                    key="monthly_budget",
                    description=(
                        "The approximate monthly amount the client can commit to "
                        "for a payment plan"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="preferred_callback_time",
                    description=(
                        "When the client would like a callback to finalize the "
                        "payment plan"
                    ),
                    field_type="text",
                    required=True,
                ),
            ],
        )


@agent.on_task_complete("dispute_details")
def on_dispute_done(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    call.hangup(
        final_instructions=(
            f"Thank {contact_name} for explaining their concern. Confirm that the "
            f"dispute has been noted and the billing team will call them back at "
            f"their preferred time, and wish them a good day, and politely say goodbye."
        )
    )


@agent.on_task_complete("payment_plan_details")
def on_plan_done(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    call.hangup(
        final_instructions=(
            f"Thank {contact_name} for their willingness to set up a plan. "
            f"Confirm that the billing team will prepare options and call them "
            f"back at their preferred time, and wish them a good day, and politely say goodbye."
        )
    )


@agent.on_action_request
def on_action_request(call: guava.Call, intent_summary: str):
    return _mid_call_intent.classify(intent_summary)


@agent.on_action("do_not_contact")
def handle_dnc(call: guava.Call) -> None:
    logging.info("Client %s requested DNC mid-call.", call.get_variable("contact_name"))
    call.hangup(
        final_instructions=(
            "Acknowledge their request. Let them know they have been removed from "
            "the contact list and will not be called again, and wish them well, and politely say goodbye."
        )
    )


@agent.on_action("speak_to_someone")
def handle_speak_to_someone(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            "Let them know a billing team member will call them back within one "
            "business day. Ask if there's a preferred time and thank them, and politely say goodbye."
        )
    )


@agent.on_outbound_failed
def on_outbound_failed(event: OutboundCallFailed) -> None:
    logging.error("Outbound call failed: %s (code %d)", event.error_reason, event.error_code)


@agent.on_session_end
def on_session_end(call: guava.Call, event: BotSessionEnded) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "use_case": "billing_followup",
        "contact_name": call.get_variable("contact_name"),
        "invoice_number": call.get_variable("invoice_number"),
        "amount_due": call.get_variable("amount_due"),
        "invoice_received": call.get_field("invoice_received"),
        "payment_intention": call.get_field("payment_intention"),
        "payment_date": call.get_field("payment_date"),
        "dispute_details": call.get_field("dispute_details"),
        "monthly_budget": call.get_field("monthly_budget"),
        "preferred_callback_time": call.get_field("preferred_callback_time"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound billing follow-up call for Hargrove & Associates"
    )
    parser.add_argument("phone", help="Phone number to dial")
    parser.add_argument("--name", required=True, help="Full name of the contact")
    parser.add_argument(
        "--invoice-number", required=True, help="Invoice number being followed up on"
    )
    parser.add_argument(
        "--amount-due", required=True, help="Outstanding amount due (e.g. $1,250.00)"
    )
    parser.add_argument(
        "--due-date", required=True, help="Original due date of the invoice"
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
            "invoice_number": args.invoice_number,
            "amount_due": args.amount_due,
            "due_date": args.due_date,
        },
    )

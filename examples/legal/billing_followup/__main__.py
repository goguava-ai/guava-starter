import argparse
import json
import logging
import os
from datetime import datetime, timezone

import guava
from guava import logging_utils

agent = guava.Agent(
    name="Sam",
    organization="Hargrove & Associates Law Firm - Billing",
    purpose=(
        "to follow up on an outstanding invoice, confirm its receipt, and "
        "collect the client's payment intention, commitment date, or dispute "
        "details in a professional and respectful manner"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(contact_full_name=call.get_variable("contact_name"))


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    if outcome == "unavailable":
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "call_type": "outbound_billing_followup",
            "status": "recipient_unavailable",
            "meta": {
                "contact_name": call.get_variable("contact_name"),
                "invoice_number": call.get_variable("invoice_number"),
                "amount_due": call.get_variable("amount_due"),
                "due_date": call.get_variable("due_date"),
            },
        }
        print(json.dumps(results, indent=2))
        logging.info("Recipient unavailable for billing follow-up call.")
        call.hangup(
            final_instructions=(
                "Leave a brief, professional voicemail identifying yourself as Sam "
                "calling from the billing department at Hargrove and Associates Law "
                f"Firm. State that you are calling regarding invoice number "
                f"{call.get_variable('invoice_number')} and ask that they return your call at their "
                "earliest convenience to discuss the matter. Provide the firm's "
                "billing department number and say goodbye."
            )
        )
    elif outcome == "available":
        call.set_task(
            "billing_followup",
            objective=(
                f"Follow up on invoice number {call.get_variable('invoice_number')} in the amount of "
                f"{call.get_variable('amount_due')}, which was due on {call.get_variable('due_date')}. Confirm the "
                "client received the invoice, determine their payment intention, and "
                "collect a payment commitment date, payment plan request, or dispute "
                "details as applicable. Remain courteous, professional, and "
                "non-confrontational throughout."
            ),
            checklist=[
                guava.Say(
                    f"Good day. I am calling from the billing department at Hargrove "
                    f"and Associates Law Firm. I am reaching out regarding invoice "
                    f"number {call.get_variable('invoice_number')} in the amount of {call.get_variable('amount_due')}, "
                    f"which had a due date of {call.get_variable('due_date')}. I wanted to follow up "
                    "to confirm you received the invoice and to discuss the status of "
                    "payment. I appreciate your time."
                ),
                guava.Field(
                    key="invoice_received",
                    description=(
                        f"Whether the client confirms they received invoice number "
                        f"{call.get_variable('invoice_number')}"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="payment_intention",
                    description=(
                        "The client's stated intention regarding payment: whether they "
                        "intend to pay in full now, would like to arrange a payment "
                        "plan, or wish to dispute the invoice or a portion of it"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="payment_date_commitment",
                    description=(
                        "If the client intends to pay, the specific date by which they "
                        "commit to submitting payment"
                    ),
                    field_type="date",
                    required=False,
                ),
                guava.Field(
                    key="dispute_reason",
                    description=(
                        "If the client is disputing the invoice or any line items, "
                        "a description of the basis for the dispute"
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="preferred_payment_method",
                    description=(
                        "The client's preferred method of payment, such as check, "
                        "credit card, ACH transfer, or online portal"
                    ),
                    field_type="text",
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("billing_followup")
def on_done(call: guava.Call) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "call_type": "outbound_billing_followup",
        "meta": {
            "contact_name": call.get_variable("contact_name"),
            "invoice_number": call.get_variable("invoice_number"),
            "amount_due": call.get_variable("amount_due"),
            "due_date": call.get_variable("due_date"),
        },
        "fields": {
            "invoice_received": call.get_field("invoice_received"),
            "payment_intention": call.get_field("payment_intention"),
            "payment_date_commitment": call.get_field("payment_date_commitment"),
            "dispute_reason": call.get_field("dispute_reason"),
            "preferred_payment_method": call.get_field("preferred_payment_method"),
        },
    }
    print(json.dumps(results, indent=2))
    logging.info("Billing follow-up results saved.")
    call.hangup(
        final_instructions=(
            "Thank the client by name for their time and for discussing the "
            "invoice. Summarize the outcome briefly — for example, confirm the "
            "payment commitment date they provided, acknowledge that a payment "
            "plan inquiry will be forwarded to the appropriate team, or confirm "
            "that their dispute has been noted and will be reviewed. Let them know "
            "they will receive any necessary follow-up by email or phone. Say "
            "goodbye professionally."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound billing follow-up call — Hargrove & Associates"
    )
    parser.add_argument("phone", help="Recipient phone number to dial")
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
    args = parser.parse_args()

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "contact_name": args.name,
            "invoice_number": args.invoice_number,
            "amount_due": args.amount_due,
            "due_date": args.due_date,
        },
    )

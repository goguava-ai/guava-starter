import guava
import os
import logging
from guava import logging_utils
import json
import argparse
import requests
from datetime import datetime, timezone


SAP_BASE_URL = os.environ["SAP_BASE_URL"]
SAP_CLIENT_ID = os.environ["SAP_CLIENT_ID"]
SAP_CLIENT_SECRET = os.environ["SAP_CLIENT_SECRET"]
SAP_TOKEN_URL = os.environ["SAP_TOKEN_URL"]


def get_access_token() -> str:
    resp = requests.post(
        SAP_TOKEN_URL,
        data={"grant_type": "client_credentials"},
        auth=(SAP_CLIENT_ID, SAP_CLIENT_SECRET),
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def get_billing_document(billing_doc_id: str) -> dict | None:
    token = get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    url = (
        f"{SAP_BASE_URL}/sap/opu/odata/sap/API_BILLING_DOCUMENT_SRV"
        f"/A_BillingDocument('{billing_doc_id}')"
    )
    resp = requests.get(url, headers=headers, params={"$format": "json"}, timeout=10)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json().get("d")


def update_billing_document_status(billing_doc_id: str, dunning_note: str) -> None:
    """Records the outcome of the dunning call in SAP as a document header note."""
    token = get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-HTTP-Method": "MERGE",
    }
    url = (
        f"{SAP_BASE_URL}/sap/opu/odata/sap/API_BILLING_DOCUMENT_SRV"
        f"/A_BillingDocument('{billing_doc_id}')"
    )
    requests.post(
        url,
        headers=headers,
        json={"CustomerPurchaseOrderReference": dunning_note[:35]},
        timeout=10,
    )


agent = guava.Agent(
    name="Morgan",
    organization="Apex Industrial Supply",
    purpose="to follow up with customers about overdue invoices and arrange payment",
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(contact_full_name=call.get_variable("contact_name"))


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    if outcome == "unavailable":
        contact_name = call.get_variable("contact_name")
        invoice_id = call.get_variable("invoice_id")
        invoice_amount = call.get_variable("invoice_amount")
        currency = call.get_variable("currency")
        logging.info(
            "Unable to reach %s for invoice %s followup", contact_name, invoice_id
        )
        call.hangup(
            final_instructions=(
                f"Leave a brief, professional voicemail for {contact_name} on behalf of "
                "Apex Industrial Supply accounts receivable. Mention that this call is regarding "
                f"invoice {invoice_id} for {invoice_amount} {currency} which is "
                f"past due. Provide the accounts receivable callback number and ask them to call "
                "at their earliest convenience. Keep the message brief and professional."
            )
        )
    elif outcome == "available":
        contact_name = call.get_variable("contact_name")
        invoice_id = call.get_variable("invoice_id")
        invoice_amount = call.get_variable("invoice_amount")
        currency = call.get_variable("currency")
        due_date = call.get_variable("due_date")
        call.set_task(
            "record_outcome",
            objective=(
                f"Follow up with {contact_name} about overdue invoice {invoice_id} "
                f"for {invoice_amount} {currency}, which was due on {due_date}. "
                "Confirm they received the invoice and determine when payment will be made."
            ),
            checklist=[
                guava.Say(
                    f"Hi {contact_name}, this is Morgan calling from Apex Industrial Supply "
                    f"accounts receivable. I'm reaching out about invoice {invoice_id} "
                    f"for {invoice_amount} {currency} which was due on {due_date}. "
                    "We haven't received payment yet and wanted to check in."
                ),
                guava.Field(
                    key="invoice_received",
                    field_type="multiple_choice",
                    description="Ask if they received and have the invoice on file.",
                    choices=["yes", "no — please resend"],
                    required=True,
                ),
                guava.Field(
                    key="payment_status",
                    field_type="multiple_choice",
                    description=(
                        "Ask about the current payment status."
                    ),
                    choices=[
                        "payment already sent",
                        "will pay within 7 days",
                        "will pay within 30 days",
                        "disputing the invoice",
                        "financial hardship — need to discuss",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="payment_notes",
                    field_type="text",
                    description=(
                        "If they have a payment reference number, dispute reason, or any other "
                        "relevant details, capture them here."
                    ),
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("record_outcome")
def on_done(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    invoice_id = call.get_variable("invoice_id")
    invoice_amount = call.get_variable("invoice_amount")
    currency = call.get_variable("currency")
    due_date = call.get_variable("due_date")

    invoice_received = call.get_field("invoice_received")
    payment_status = call.get_field("payment_status")
    payment_notes = call.get_field("payment_notes") or ""

    logging.info(
        "Invoice followup outcome for %s (invoice %s): received=%s, status=%s",
        contact_name, invoice_id, invoice_received, payment_status,
    )

    outcome = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": "Morgan",
        "use_case": "overdue_invoice_followup",
        "contact": contact_name,
        "invoice_id": invoice_id,
        "invoice_amount": f"{invoice_amount} {currency}",
        "due_date": due_date,
        "invoice_received": invoice_received,
        "payment_status": payment_status,
        "payment_notes": payment_notes,
    }
    print(json.dumps(outcome, indent=2))

    # Record the dunning call result in SAP
    dunning_note = f"Dunning call {datetime.now(timezone.utc).strftime('%Y%m%d')}: {payment_status}"
    try:
        update_billing_document_status(invoice_id, dunning_note)
        logging.info("Dunning outcome recorded for invoice %s", invoice_id)
    except Exception as e:
        logging.warning("Failed to update SAP billing document: %s", e)

    if payment_status == "payment already sent":
        call.hangup(
            final_instructions=(
                f"Thank {contact_name} and let them know we'll verify the payment on our end "
                f"and update the record. If there's a reference number, let them know we've noted it. "
                "Apologize for any confusion and thank them for their continued partnership."
            )
        )
    elif payment_status in ("will pay within 7 days", "will pay within 30 days"):
        timeline = payment_status.replace("will pay ", "")
        call.hangup(
            final_instructions=(
                f"Thank {contact_name} for letting us know and confirm that payment "
                f"is expected {timeline}. Let them know our team will be in touch if we "
                "don't see it by then. Wish them a great day."
            )
        )
    elif payment_status == "disputing the invoice":
        call.hangup(
            final_instructions=(
                f"Acknowledge {contact_name}'s dispute and let them know our accounts "
                "receivable team will review the details and follow up within two business days. "
                "Assure them the dispute is noted and no collections action will be taken "
                "while it's under review. Thank them for letting us know."
            )
        )
    elif payment_status == "no — please resend":
        call.hangup(
            final_instructions=(
                f"Apologize that {contact_name} didn't receive the invoice and let them "
                "know we will resend it to the email address on file today. "
                "Ask them to allow up to one business day for delivery. "
                "Thank them for their patience."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {contact_name} for being candid. Let them know we want to work "
                "with them and that an accounts receivable specialist will reach out to "
                "discuss options. We appreciate their honesty and their partnership."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound overdue invoice follow-up call using SAP billing data."
    )
    parser.add_argument("phone", help="Customer phone number (E.164, e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Contact full name")
    parser.add_argument("--invoice-id", required=True, help="SAP billing document number")
    parser.add_argument("--amount", required=True, help="Invoice amount (e.g. 4250.00)")
    parser.add_argument("--currency", default="USD", help="Currency code (default: USD)")
    parser.add_argument("--due-date", required=True, help="Invoice due date (YYYY-MM-DD)")
    args = parser.parse_args()

    logging.info(
        "Initiating overdue invoice followup call to %s for invoice %s (%s %s, due %s)",
        args.name, args.invoice_id, args.amount, args.currency, args.due_date,
    )

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "contact_name": args.name,
            "invoice_id": args.invoice_id,
            "invoice_amount": args.amount,
            "currency": args.currency,
            "due_date": args.due_date,
        },
    )

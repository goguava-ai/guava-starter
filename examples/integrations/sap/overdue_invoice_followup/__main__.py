import guava
import os
import logging
import json
import argparse
import requests
from datetime import datetime

logging.basicConfig(level=logging.INFO)

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


class OverdueInvoiceFollowupController(guava.CallController):
    def __init__(self, contact_name: str, invoice_id: str, invoice_amount: str, currency: str, due_date: str):
        super().__init__()
        self.contact_name = contact_name
        self.invoice_id = invoice_id
        self.invoice_amount = invoice_amount
        self.currency = currency
        self.due_date = due_date

        self.set_persona(
            organization_name="Apex Industrial Supply",
            agent_name="Morgan",
            agent_purpose=(
                "to follow up with customers about overdue invoices and arrange payment"
            ),
        )

        self.reach_person(
            contact_full_name=self.contact_name,
            on_success=self.begin_followup,
            on_failure=self.recipient_unavailable,
        )

    def begin_followup(self):
        self.set_task(
            objective=(
                f"Follow up with {self.contact_name} about overdue invoice {self.invoice_id} "
                f"for {self.invoice_amount} {self.currency}, which was due on {self.due_date}. "
                "Confirm they received the invoice and determine when payment will be made."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.contact_name}, this is Morgan calling from Apex Industrial Supply "
                    f"accounts receivable. I'm reaching out about invoice {self.invoice_id} "
                    f"for {self.invoice_amount} {self.currency} which was due on {self.due_date}. "
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
            on_complete=self.record_outcome,
        )

    def record_outcome(self):
        invoice_received = self.get_field("invoice_received")
        payment_status = self.get_field("payment_status")
        payment_notes = self.get_field("payment_notes") or ""

        logging.info(
            "Invoice followup outcome for %s (invoice %s): received=%s, status=%s",
            self.contact_name, self.invoice_id, invoice_received, payment_status,
        )

        outcome = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "agent": "Morgan",
            "use_case": "overdue_invoice_followup",
            "contact": self.contact_name,
            "invoice_id": self.invoice_id,
            "invoice_amount": f"{self.invoice_amount} {self.currency}",
            "due_date": self.due_date,
            "invoice_received": invoice_received,
            "payment_status": payment_status,
            "payment_notes": payment_notes,
        }
        print(json.dumps(outcome, indent=2))

        # Record the dunning call result in SAP
        dunning_note = f"Dunning call {datetime.utcnow().strftime('%Y%m%d')}: {payment_status}"
        try:
            update_billing_document_status(self.invoice_id, dunning_note)
            logging.info("Dunning outcome recorded for invoice %s", self.invoice_id)
        except Exception as e:
            logging.warning("Failed to update SAP billing document: %s", e)

        if payment_status == "payment already sent":
            self.hangup(
                final_instructions=(
                    f"Thank {self.contact_name} and let them know we'll verify the payment on our end "
                    f"and update the record. If there's a reference number, let them know we've noted it. "
                    "Apologize for any confusion and thank them for their continued partnership."
                )
            )
        elif payment_status in ("will pay within 7 days", "will pay within 30 days"):
            timeline = payment_status.replace("will pay ", "")
            self.hangup(
                final_instructions=(
                    f"Thank {self.contact_name} for letting us know and confirm that payment "
                    f"is expected {timeline}. Let them know our team will be in touch if we "
                    "don't see it by then. Wish them a great day."
                )
            )
        elif payment_status == "disputing the invoice":
            self.hangup(
                final_instructions=(
                    f"Acknowledge {self.contact_name}'s dispute and let them know our accounts "
                    "receivable team will review the details and follow up within two business days. "
                    "Assure them the dispute is noted and no collections action will be taken "
                    "while it's under review. Thank them for letting us know."
                )
            )
        elif payment_status == "no — please resend":
            self.hangup(
                final_instructions=(
                    f"Apologize that {self.contact_name} didn't receive the invoice and let them "
                    "know we will resend it to the email address on file today. "
                    "Ask them to allow up to one business day for delivery. "
                    "Thank them for their patience."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    f"Thank {self.contact_name} for being candid. Let them know we want to work "
                    "with them and that an accounts receivable specialist will reach out to "
                    "discuss options. We appreciate their honesty and their partnership."
                )
            )

    def recipient_unavailable(self):
        logging.info(
            "Unable to reach %s for invoice %s followup", self.contact_name, self.invoice_id
        )
        self.hangup(
            final_instructions=(
                f"Leave a brief, professional voicemail for {self.contact_name} on behalf of "
                "Apex Industrial Supply accounts receivable. Mention that this call is regarding "
                f"invoice {self.invoice_id} for {self.invoice_amount} {self.currency} which is "
                f"past due. Provide the accounts receivable callback number and ask them to call "
                "at their earliest convenience. Keep the message brief and professional."
            )
        )


if __name__ == "__main__":
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

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=OverdueInvoiceFollowupController(
            contact_name=args.name,
            invoice_id=args.invoice_id,
            invoice_amount=args.amount,
            currency=args.currency,
            due_date=args.due_date,
        ),
    )

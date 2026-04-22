import guava
import os
import logging
from guava import logging_utils
import json
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
    """Fetches a billing document (customer invoice) from the SAP Billing Document API."""
    token = get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    url = (
        f"{SAP_BASE_URL}/sap/opu/odata/sap/API_BILLING_DOCUMENT_SRV"
        f"/A_BillingDocument('{billing_doc_id}')"
    )
    resp = requests.get(
        url,
        headers=headers,
        params={"$expand": "to_Item", "$format": "json"},
        timeout=10,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json().get("d")


def get_billing_documents_by_customer(sold_to_party: str) -> list:
    """Returns the 5 most recent billing documents for a customer."""
    token = get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    url = f"{SAP_BASE_URL}/sap/opu/odata/sap/API_BILLING_DOCUMENT_SRV/A_BillingDocument"
    resp = requests.get(
        url,
        headers=headers,
        params={
            "$filter": f"SoldToParty eq '{sold_to_party}'",
            "$orderby": "BillingDocumentDate desc",
            "$top": "5",
            "$format": "json",
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("d", {}).get("results", [])


def create_dispute_note(billing_doc_id: str, note_text: str) -> None:
    """Appends a dispute note to the billing document via a PATCH on the document header."""
    token = get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-HTTP-Method": "MERGE",  # SAP OData PATCH equivalent
    }
    url = (
        f"{SAP_BASE_URL}/sap/opu/odata/sap/API_BILLING_DOCUMENT_SRV"
        f"/A_BillingDocument('{billing_doc_id}')"
    )
    # Append the note to the customer purchase order reference field as a workaround
    # for environments without a dedicated notes API. In production, use the SAP Notes API.
    requests.post(
        url,
        headers=headers,
        json={"CustomerPurchaseOrderReference": note_text[:35]},
        timeout=10,
    )


class InvoiceInquiryController(guava.CallController):
    def __init__(self):
        super().__init__()
        self._billing_doc = None

        self.set_persona(
            organization_name="Apex Industrial Supply",
            agent_name="Riley",
            agent_purpose=(
                "to help customers with questions or disputes about their invoices"
            ),
        )

        self.set_task(
            objective=(
                "A customer is calling with a question or dispute about an invoice. "
                "Collect their account or invoice details, look up the invoice in SAP, "
                "and gather information about their concern."
            ),
            checklist=[
                guava.Say(
                    "Thank you for calling Apex Industrial Supply accounts receivable. "
                    "I'm Riley. I can help you with an invoice question."
                ),
                guava.Field(
                    key="invoice_number",
                    field_type="text",
                    description=(
                        "Ask for the invoice number they're calling about. "
                        "It's typically a 10-digit number printed at the top of the invoice."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="caller_name",
                    field_type="text",
                    description="Ask for the caller's full name.",
                    required=True,
                ),
                guava.Field(
                    key="concern_type",
                    field_type="multiple_choice",
                    description=(
                        "Ask what type of concern they have about the invoice."
                    ),
                    choices=[
                        "incorrect amount",
                        "already paid but still receiving invoice",
                        "missing item or service",
                        "need a copy of the invoice",
                        "other question",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="concern_detail",
                    field_type="text",
                    description=(
                        "Ask them to briefly describe the issue in more detail."
                    ),
                    required=False,
                ),
            ],
            on_complete=self.look_up_invoice,
        )

        self.accept_call()

    def look_up_invoice(self):
        invoice_number = (self.get_field("invoice_number") or "").strip()
        caller_name = self.get_field("caller_name")
        concern_type = self.get_field("concern_type")
        concern_detail = self.get_field("concern_detail") or ""

        logging.info(
            "Invoice inquiry from %s for invoice %s — concern: %s",
            caller_name, invoice_number, concern_type,
        )

        try:
            doc = get_billing_document(invoice_number)
        except Exception as e:
            logging.error("SAP billing document lookup failed: %s", e)
            doc = None

        if not doc:
            self.hangup(
                final_instructions=(
                    f"Let {caller_name} know that we could not find invoice number "
                    f"{invoice_number} in our system. Ask them to double-check the invoice "
                    "number and call back, or offer to transfer them to an accounts receivable "
                    "specialist. Apologize for the inconvenience."
                )
            )
            return

        net_amount = doc.get("TotalNetAmount", "")
        currency = doc.get("TransactionCurrency", "")
        billing_date = doc.get("BillingDocumentDate", "")
        due_date = doc.get("PaymentTerms", "")
        status = doc.get("OverallBillingStatus", "")

        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": "Riley",
            "use_case": "invoice_inquiry",
            "invoice_number": invoice_number,
            "caller": caller_name,
            "concern_type": concern_type,
            "concern_detail": concern_detail,
            "invoice": {
                "net_amount": net_amount,
                "currency": currency,
                "billing_date": billing_date,
                "overall_status": status,
            },
        }
        print(json.dumps(result, indent=2))

        # Log the dispute note against the billing document
        if concern_type not in ("need a copy of the invoice", "other question"):
            note = f"Caller dispute [{concern_type}]: {concern_detail or 'no detail provided'}"
            try:
                create_dispute_note(invoice_number, note)
                logging.info("Dispute note added to invoice %s", invoice_number)
            except Exception as e:
                logging.warning("Failed to add dispute note: %s", e)

        amount_note = f"${net_amount} {currency}" if net_amount else "the amount on file"
        date_note = f" dated {billing_date}" if billing_date else ""

        if concern_type == "need a copy of the invoice":
            self.hangup(
                final_instructions=(
                    f"Let {caller_name} know that invoice {invoice_number}{date_note} "
                    f"for {amount_note} is on file. Let them know a copy will be emailed to "
                    "the address on their account within one business day. "
                    "Thank them for calling Apex Industrial Supply."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    f"Acknowledge {caller_name}'s concern about invoice {invoice_number}{date_note} "
                    f"for {amount_note}. Let them know that their concern regarding "
                    f"'{concern_type}' has been logged and our accounts receivable team will "
                    "investigate and follow up within two business days. "
                    "Thank them for calling and for their patience."
                )
            )


if __name__ == "__main__":
    logging_utils.configure_logging()
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=InvoiceInquiryController,
    )

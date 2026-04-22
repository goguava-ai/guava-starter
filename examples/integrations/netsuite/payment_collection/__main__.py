import guava
import os
import logging
import json
import argparse
import requests
from requests_oauthlib import OAuth1
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)

NS_ACCOUNT_ID = os.environ["NETSUITE_ACCOUNT_ID"]
NS_CONSUMER_KEY = os.environ["NETSUITE_CONSUMER_KEY"]
NS_CONSUMER_SECRET = os.environ["NETSUITE_CONSUMER_SECRET"]
NS_TOKEN_KEY = os.environ["NETSUITE_TOKEN_KEY"]
NS_TOKEN_SECRET = os.environ["NETSUITE_TOKEN_SECRET"]

_acct = NS_ACCOUNT_ID.lower().replace("_", "-")
REST_BASE = f"https://{_acct}.suitetalk.api.netsuite.com/services/rest/record/v1"


def _auth() -> OAuth1:
    return OAuth1(
        NS_CONSUMER_KEY,
        NS_CONSUMER_SECRET,
        NS_TOKEN_KEY,
        NS_TOKEN_SECRET,
        signature_method="HMAC-SHA256",
        realm=NS_ACCOUNT_ID,
    )


def get_invoice(invoice_id: str) -> dict | None:
    resp = requests.get(
        f"{REST_BASE}/invoice/{invoice_id}",
        auth=_auth(),
        timeout=10,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def apply_customer_payment(customer_id: str, invoice_id: str, amount: float, memo: str) -> dict:
    """Creates a CustomerPayment record in NetSuite applied to the specified invoice."""
    payload = {
        "customer": {"id": customer_id},
        "applyList": {
            "apply": [
                {
                    "doc": {"id": invoice_id},
                    "apply": True,
                    "amount": amount,
                }
            ]
        },
        "memo": memo,
        "trandate": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }
    resp = requests.post(
        f"{REST_BASE}/customerPayment",
        auth=_auth(),
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()
    location = resp.headers.get("Location", "")
    payment_id = location.rstrip("/").split("/")[-1] if location else ""
    return {"payment_id": payment_id, "status": "created"}


def add_invoice_memo(invoice_id: str, memo: str) -> None:
    """Appends a collection call note to the invoice memo field."""
    requests.patch(
        f"{REST_BASE}/invoice/{invoice_id}",
        auth=_auth(),
        json={"memo": memo},
        timeout=10,
    )


class PaymentCollectionController(guava.CallController):
    def __init__(
        self,
        contact_name: str,
        customer_id: str,
        invoice_id: str,
        invoice_number: str,
        amount_due: str,
        currency: str,
        due_date: str,
    ):
        super().__init__()
        self.contact_name = contact_name
        self.customer_id = customer_id
        self.invoice_id = invoice_id
        self.invoice_number = invoice_number
        self.amount_due = amount_due
        self.currency = currency
        self.due_date = due_date

        self.set_persona(
            organization_name="Meridian Solutions",
            agent_name="Dana",
            agent_purpose=(
                "to follow up with customers about outstanding invoice balances and arrange payment"
            ),
        )

        self.reach_person(
            contact_full_name=self.contact_name,
            on_success=self.begin_collection,
            on_failure=self.recipient_unavailable,
        )

    def begin_collection(self):
        first_name = self.contact_name.split()[0] if self.contact_name else "there"

        self.set_task(
            objective=(
                f"Collect payment or a payment commitment from {self.contact_name} for "
                f"invoice {self.invoice_number} totaling ${self.amount_due} {self.currency}, "
                f"which was due on {self.due_date}."
            ),
            checklist=[
                guava.Say(
                    f"Hi {first_name}, this is Dana calling from Meridian Solutions accounts "
                    f"receivable. I'm reaching out about invoice {self.invoice_number} "
                    f"for ${self.amount_due} {self.currency} which was due on {self.due_date}. "
                    "I wanted to check in and see how we can help get this resolved."
                ),
                guava.Field(
                    key="payment_status",
                    field_type="multiple_choice",
                    description="Ask about the status of payment for this invoice.",
                    choices=[
                        "payment already sent",
                        "can pay now by credit card",
                        "will pay within 7 days",
                        "will pay within 30 days",
                        "disputing the invoice",
                        "need a payment plan",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="payment_reference",
                    field_type="text",
                    description=(
                        "If payment has already been sent, ask for a payment reference or "
                        "check number. Optional for other statuses."
                    ),
                    required=False,
                ),
            ],
            on_complete=self.handle_payment_response,
        )

    def handle_payment_response(self):
        payment_status = self.get_field("payment_status")
        payment_reference = self.get_field("payment_reference") or ""
        first_name = self.contact_name.split()[0] if self.contact_name else "there"

        logging.info(
            "Payment collection outcome for invoice %s: status=%s",
            self.invoice_number, payment_status,
        )

        memo_note = (
            f"Collection call {datetime.now(timezone.utc).strftime('%Y-%m-%d')}: "
            f"{payment_status}"
            + (f" — ref: {payment_reference}" if payment_reference else "")
        )

        try:
            add_invoice_memo(self.invoice_id, memo_note)
            logging.info("Memo added to invoice %s", self.invoice_id)
        except Exception as e:
            logging.warning("Failed to update invoice memo: %s", e)

        outcome = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": "Dana",
            "use_case": "payment_collection",
            "contact": self.contact_name,
            "invoice_id": self.invoice_id,
            "invoice_number": self.invoice_number,
            "amount_due": f"{self.amount_due} {self.currency}",
            "due_date": self.due_date,
            "payment_status": payment_status,
            "payment_reference": payment_reference,
        }
        print(json.dumps(outcome, indent=2))

        if payment_status == "payment already sent":
            self.hangup(
                final_instructions=(
                    f"Thank {first_name} and let them know we'll look for the payment on our "
                    "end and update the record. If there's a reference number, confirm we've "
                    "noted it. Apologize for any confusion and thank them for their partnership."
                )
            )
        elif payment_status == "can pay now by credit card":
            self.hangup(
                final_instructions=(
                    f"Let {first_name} know you'll transfer them to our payment processing "
                    "team who can securely take their credit card information. "
                    "Thank them for taking care of this right away."
                )
            )
        elif payment_status in ("will pay within 7 days", "will pay within 30 days"):
            timeline = payment_status.replace("will pay ", "")
            self.hangup(
                final_instructions=(
                    f"Thank {first_name} for the commitment and let them know we've noted "
                    f"that payment is expected {timeline}. Let them know our team will follow "
                    "up if we don't see it by then. Wish them a great day."
                )
            )
        elif payment_status == "disputing the invoice":
            self.hangup(
                final_instructions=(
                    f"Acknowledge {first_name}'s dispute and let them know our accounts "
                    "receivable team will review the invoice details and follow up within "
                    "two business days. Assure them no late fees will accrue while the "
                    "dispute is under review. Thank them for letting us know."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    f"Thank {first_name} for being candid. Let them know our team will "
                    "reach out by email with payment plan options tailored to their situation. "
                    "We value their partnership and want to work with them. Wish them well."
                )
            )

    def recipient_unavailable(self):
        logging.info(
            "Unable to reach %s for invoice %s collection", self.contact_name, self.invoice_number
        )
        memo_note = f"Collection voicemail left {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
        try:
            add_invoice_memo(self.invoice_id, memo_note)
        except Exception as e:
            logging.warning("Failed to update invoice memo after voicemail: %s", e)

        self.hangup(
            final_instructions=(
                f"Leave a professional voicemail for {self.contact_name} from Meridian "
                "Solutions accounts receivable. Mention invoice {self.invoice_number} "
                f"for ${self.amount_due} {self.currency} and ask them to call back. "
                "Provide the AR department callback number. Keep it brief and professional."
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Outbound payment collection call using NetSuite invoice data."
    )
    parser.add_argument("phone", help="Customer phone number (E.164, e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Contact full name")
    parser.add_argument("--customer-id", required=True, help="NetSuite customer internal ID")
    parser.add_argument("--invoice-id", required=True, help="NetSuite invoice internal ID")
    parser.add_argument("--invoice-number", required=True, help="Invoice transaction number (tranid)")
    parser.add_argument("--amount", required=True, help="Amount due (e.g. 3200.00)")
    parser.add_argument("--currency", default="USD", help="Currency code")
    parser.add_argument("--due-date", required=True, help="Invoice due date (YYYY-MM-DD)")
    args = parser.parse_args()

    logging.info(
        "Initiating payment collection call to %s for invoice %s ($%s, due %s)",
        args.name, args.invoice_number, args.amount, args.due_date,
    )

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=PaymentCollectionController(
            contact_name=args.name,
            customer_id=args.customer_id,
            invoice_id=args.invoice_id,
            invoice_number=args.invoice_number,
            amount_due=args.amount,
            currency=args.currency,
            due_date=args.due_date,
        ),
    )

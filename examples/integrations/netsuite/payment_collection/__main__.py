import guava
import os
import logging
from guava import logging_utils
import json
import argparse
import requests
from requests_oauthlib import OAuth1
from datetime import datetime, timezone


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


agent = guava.Agent(
    name="Dana",
    organization="Meridian Solutions",
    purpose=(
        "to follow up with customers about outstanding invoice balances and arrange payment"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(contact_full_name=call.get_variable("contact_name"))


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    contact_name = call.get_variable("contact_name")
    invoice_id = call.get_variable("invoice_id")
    invoice_number = call.get_variable("invoice_number")
    amount_due = call.get_variable("amount_due")
    currency = call.get_variable("currency")
    due_date = call.get_variable("due_date")

    if outcome == "unavailable":
        logging.info(
            "Unable to reach %s for invoice %s collection", contact_name, invoice_number
        )
        memo_note = f"Collection voicemail left {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
        try:
            add_invoice_memo(invoice_id, memo_note)
        except Exception as e:
            logging.warning("Failed to update invoice memo after voicemail: %s", e)

        call.hangup(
            final_instructions=(
                f"Leave a professional voicemail for {contact_name} from Meridian "
                "Solutions accounts receivable. Mention invoice {invoice_number} "
                f"for ${amount_due} {currency} and ask them to call back. "
                "Provide the AR department callback number. Keep it brief and professional."
            )
        )
    elif outcome == "available":
        first_name = contact_name.split()[0] if contact_name else "there"

        call.set_task(
            "payment_collection",
            objective=(
                f"Collect payment or a payment commitment from {contact_name} for "
                f"invoice {invoice_number} totaling ${amount_due} {currency}, "
                f"which was due on {due_date}."
            ),
            checklist=[
                guava.Say(
                    f"Hi {first_name}, this is Dana calling from Meridian Solutions accounts "
                    f"receivable. I'm reaching out about invoice {invoice_number} "
                    f"for ${amount_due} {currency} which was due on {due_date}. "
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
        )


@agent.on_task_complete("payment_collection")
def on_payment_collection_done(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    invoice_id = call.get_variable("invoice_id")
    invoice_number = call.get_variable("invoice_number")
    amount_due = call.get_variable("amount_due")
    currency = call.get_variable("currency")
    due_date = call.get_variable("due_date")

    payment_status = call.get_field("payment_status")
    payment_reference = call.get_field("payment_reference") or ""
    first_name = contact_name.split()[0] if contact_name else "there"

    logging.info(
        "Payment collection outcome for invoice %s: status=%s",
        invoice_number, payment_status,
    )

    memo_note = (
        f"Collection call {datetime.now(timezone.utc).strftime('%Y-%m-%d')}: "
        f"{payment_status}"
        + (f" — ref: {payment_reference}" if payment_reference else "")
    )

    try:
        add_invoice_memo(invoice_id, memo_note)
        logging.info("Memo added to invoice %s", invoice_id)
    except Exception as e:
        logging.warning("Failed to update invoice memo: %s", e)

    outcome = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": "Dana",
        "use_case": "payment_collection",
        "contact": contact_name,
        "invoice_id": invoice_id,
        "invoice_number": invoice_number,
        "amount_due": f"{amount_due} {currency}",
        "due_date": due_date,
        "payment_status": payment_status,
        "payment_reference": payment_reference,
    }
    print(json.dumps(outcome, indent=2))

    if payment_status == "payment already sent":
        call.hangup(
            final_instructions=(
                f"Thank {first_name} and let them know we'll look for the payment on our "
                "end and update the record. If there's a reference number, confirm we've "
                "noted it. Apologize for any confusion and thank them for their partnership."
            )
        )
    elif payment_status == "can pay now by credit card":
        call.hangup(
            final_instructions=(
                f"Let {first_name} know you'll transfer them to our payment processing "
                "team who can securely take their credit card information. "
                "Thank them for taking care of this right away."
            )
        )
    elif payment_status in ("will pay within 7 days", "will pay within 30 days"):
        timeline = payment_status.replace("will pay ", "")
        call.hangup(
            final_instructions=(
                f"Thank {first_name} for the commitment and let them know we've noted "
                f"that payment is expected {timeline}. Let them know our team will follow "
                "up if we don't see it by then. Wish them a great day."
            )
        )
    elif payment_status == "disputing the invoice":
        call.hangup(
            final_instructions=(
                f"Acknowledge {first_name}'s dispute and let them know our accounts "
                "receivable team will review the invoice details and follow up within "
                "two business days. Assure them no late fees will accrue while the "
                "dispute is under review. Thank them for letting us know."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {first_name} for being candid. Let them know our team will "
                "reach out by email with payment plan options tailored to their situation. "
                "We value their partnership and want to work with them. Wish them well."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
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

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "contact_name": args.name,
            "customer_id": args.customer_id,
            "invoice_id": args.invoice_id,
            "invoice_number": args.invoice_number,
            "amount_due": args.amount,
            "currency": args.currency,
            "due_date": args.due_date,
        },
    )

import guava
import os
import logging
from guava import logging_utils
import argparse
import requests


BASE_URL = os.environ.get("SQUARE_BASE_URL", "https://connect.squareupsandbox.com")
SQUARE_VERSION = "2024-01-18"


def get_headers() -> dict:
    return {
        "Authorization": f"Bearer {os.environ['SQUARE_ACCESS_TOKEN']}",
        "Square-Version": SQUARE_VERSION,
        "Content-Type": "application/json",
    }


def get_invoice(invoice_id: str) -> dict | None:
    resp = requests.get(
        f"{BASE_URL}/v2/invoices/{invoice_id}",
        headers=get_headers(),
        timeout=10,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json().get("invoice")


def publish_invoice(invoice_id: str, version: int) -> dict | None:
    """Publishes (sends) the invoice to the customer — triggers Square to send the payment link."""
    resp = requests.post(
        f"{BASE_URL}/v2/invoices/{invoice_id}/publish",
        headers=get_headers(),
        json={"version": version, "idempotency_key": invoice_id + "_publish"},
        timeout=10,
    )
    if not resp.ok:
        return None
    return resp.json().get("invoice")


def format_amount(amount_money: dict) -> str:
    amount = amount_money.get("amount", 0)
    currency = amount_money.get("currency", "USD")
    return f"${amount / 100:,.2f} {currency}"


agent = guava.Agent(
    name="Drew",
    organization="Harbor Market",
    purpose=(
        "to help Harbor Market collect payment on outstanding invoices"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    invoice_id = call.get_variable("invoice_id")

    invoice = None
    try:
        invoice = get_invoice(invoice_id)
        logging.info(
            "Invoice %s loaded: status=%s",
            invoice_id,
            invoice.get("status") if invoice else "not found",
        )
    except Exception as e:
        logging.error("Failed to load invoice %s: %s", invoice_id, e)

    call.set_variable("invoice", invoice)

    call.reach_person(contact_full_name=customer_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    customer_name = call.get_variable("customer_name")
    invoice_id = call.get_variable("invoice_id")

    if outcome == "unavailable":
        logging.info("Unable to reach %s for invoice collection.", customer_name)
        call.hangup(
            final_instructions=(
                f"Leave a professional voicemail for {customer_name} from Harbor Market. "
                f"Let them know you're calling about invoice {invoice_id} and ask them "
                "to check their email for the invoice link or call back. Keep it concise."
            )
        )
    elif outcome == "available":
        invoice = call.get_variable("invoice")
        if not invoice:
            call.hangup(
                final_instructions=(
                    f"Let {customer_name} know you're calling from Harbor Market about an "
                    "outstanding invoice, but the details aren't loading right now. "
                    "Ask them to check their email for the invoice or call back during business hours."
                )
            )
            return

        status = invoice.get("status", "UNKNOWN")
        if status == "PAID":
            logging.info("Invoice %s is already paid.", invoice_id)
            call.hangup(
                final_instructions=(
                    f"Let {customer_name} know you were calling about invoice {invoice_id} "
                    "from Harbor Market, but it looks like it's already been paid. "
                    "Thank them and wish them a great day."
                )
            )
            return

        payment_requests = invoice.get("payment_requests", [])
        amount_str = ""
        if payment_requests:
            computed_amount = payment_requests[0].get("computed_amount_money", {})
            amount_str = format_amount(computed_amount) if computed_amount else ""
        due_date = invoice.get("payment_requests", [{}])[0].get("due_date", "") if payment_requests else ""
        invoice_number = invoice.get("invoice_number", invoice_id)

        call.set_task(
            "handle_intent",
            objective=(
                f"Reach {customer_name} about unpaid Harbor Market invoice #{invoice_number}"
                + (f" for {amount_str}" if amount_str else "")
                + (f" due {due_date}" if due_date else "")
                + ". Prompt payment and re-send the invoice link if they're ready to pay."
            ),
            checklist=[
                guava.Say(
                    f"Hi {customer_name}, this is Drew calling from Harbor Market. "
                    f"I'm reaching out about invoice #{invoice_number}"
                    + (f" for {amount_str}" if amount_str else "")
                    + (f" which was due {due_date}" if due_date else "")
                    + ". I wanted to check in and see if you have any questions about it."
                ),
                guava.Field(
                    key="aware",
                    field_type="multiple_choice",
                    description="Ask if they received and are aware of the invoice.",
                    choices=["yes, I have it", "no, didn't receive it", "already paid"],
                    required=True,
                ),
                guava.Field(
                    key="payment_intent",
                    field_type="multiple_choice",
                    description="Ask when they plan to pay or if they'd like the invoice resent.",
                    choices=["paying today", "paying this week", "need to dispute", "resend the invoice"],
                    required=True,
                ),
            ],
        )


@agent.on_task_complete("handle_intent")
def handle_intent(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    invoice_id = call.get_variable("invoice_id")
    aware = call.get_field("aware") or ""
    intent = call.get_field("payment_intent") or ""

    # Reconstruct invoice_number and amount_str from stored invoice
    invoice = call.get_variable("invoice")
    invoice_number = invoice.get("invoice_number", invoice_id) if invoice else invoice_id
    payment_requests = invoice.get("payment_requests", []) if invoice else []
    amount_str = ""
    if payment_requests:
        computed_amount = payment_requests[0].get("computed_amount_money", {})
        amount_str = format_amount(computed_amount) if computed_amount else ""

    logging.info(
        "Invoice collection outcome for %s — aware: %s, intent: %s",
        invoice_id, aware, intent,
    )

    if "already paid" in aware:
        call.hangup(
            final_instructions=(
                f"Apologize for the confusion and let {customer_name} know you'll verify "
                "the payment on your end. Thank them for their time and wish them a great day."
            )
        )
        return

    if "resend" in intent or "didn't receive" in aware:
        published = None
        try:
            version = invoice.get("version", 0) if invoice else 0
            published = publish_invoice(invoice_id, version)
            logging.info("Invoice %s republished: %s", invoice_id, bool(published))
        except Exception as e:
            logging.error("Failed to republish invoice %s: %s", invoice_id, e)

        call.hangup(
            final_instructions=(
                f"Let {customer_name} know the invoice has been resent to their email on file. "
                "They can click the link in the email to pay securely. "
                "Thank them and wish them a great day."
            )
        )
        return

    if "dispute" in intent:
        call.hangup(
            final_instructions=(
                f"Let {customer_name} know you've noted their dispute. "
                "Our billing team will review and follow up by email within one business day. "
                "Thank them for letting us know."
            )
        )
        return

    call.hangup(
        final_instructions=(
            f"Thank {customer_name} for their time and their commitment to pay invoice #{invoice_number}"
            + (f" for {amount_str}" if amount_str else "")
            + ". Let them know they can use the link in their invoice email to pay securely. "
            "Wish them a great day."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(description="Outbound Square invoice collection call.")
    parser.add_argument("phone", help="Customer phone number (E.164)")
    parser.add_argument("--name", required=True, help="Customer's full name")
    parser.add_argument("--invoice-id", required=True, help="Square invoice ID")
    args = parser.parse_args()

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "customer_name": args.name,
            "invoice_id": args.invoice_id,
        },
    )

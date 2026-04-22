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


class InvoiceCollectionController(guava.CallController):
    def __init__(self, customer_name: str, invoice_id: str):
        super().__init__()
        self.customer_name = customer_name
        self.invoice_id = invoice_id
        self.invoice = None

        try:
            self.invoice = get_invoice(invoice_id)
            logging.info(
                "Invoice %s loaded: status=%s",
                invoice_id,
                self.invoice.get("status") if self.invoice else "not found",
            )
        except Exception as e:
            logging.error("Failed to load invoice %s: %s", invoice_id, e)

        self.set_persona(
            organization_name="Harbor Market",
            agent_name="Drew",
            agent_purpose=(
                "to help Harbor Market collect payment on outstanding invoices"
            ),
        )

        self.reach_person(
            contact_full_name=self.customer_name,
            on_success=self.present_invoice,
            on_failure=self.leave_voicemail,
        )

    def present_invoice(self):
        if not self.invoice:
            self.hangup(
                final_instructions=(
                    f"Let {self.customer_name} know you're calling from Harbor Market about an "
                    "outstanding invoice, but the details aren't loading right now. "
                    "Ask them to check their email for the invoice or call back during business hours."
                )
            )
            return

        status = self.invoice.get("status", "UNKNOWN")
        if status == "PAID":
            logging.info("Invoice %s is already paid.", self.invoice_id)
            self.hangup(
                final_instructions=(
                    f"Let {self.customer_name} know you were calling about invoice {self.invoice_id} "
                    "from Harbor Market, but it looks like it's already been paid. "
                    "Thank them and wish them a great day."
                )
            )
            return

        payment_requests = self.invoice.get("payment_requests", [])
        amount_str = ""
        if payment_requests:
            computed_amount = payment_requests[0].get("computed_amount_money", {})
            amount_str = format_amount(computed_amount) if computed_amount else ""
        due_date = self.invoice.get("payment_requests", [{}])[0].get("due_date", "") if payment_requests else ""
        invoice_number = self.invoice.get("invoice_number", self.invoice_id)

        self.set_task(
            objective=(
                f"Reach {self.customer_name} about unpaid Harbor Market invoice #{invoice_number}"
                + (f" for {amount_str}" if amount_str else "")
                + (f" due {due_date}" if due_date else "")
                + ". Prompt payment and re-send the invoice link if they're ready to pay."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.customer_name}, this is Drew calling from Harbor Market. "
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
            on_complete=lambda: self.handle_intent(invoice_number, amount_str),
        )

    def handle_intent(self, invoice_number: str, amount_str: str):
        aware = self.get_field("aware") or ""
        intent = self.get_field("payment_intent") or ""

        logging.info(
            "Invoice collection outcome for %s — aware: %s, intent: %s",
            self.invoice_id, aware, intent,
        )

        if "already paid" in aware:
            self.hangup(
                final_instructions=(
                    f"Apologize for the confusion and let {self.customer_name} know you'll verify "
                    "the payment on your end. Thank them for their time and wish them a great day."
                )
            )
            return

        if "resend" in intent or "didn't receive" in aware:
            published = None
            try:
                version = self.invoice.get("version", 0) if self.invoice else 0
                published = publish_invoice(self.invoice_id, version)
                logging.info("Invoice %s republished: %s", self.invoice_id, bool(published))
            except Exception as e:
                logging.error("Failed to republish invoice %s: %s", self.invoice_id, e)

            self.hangup(
                final_instructions=(
                    f"Let {self.customer_name} know the invoice has been resent to their email on file. "
                    "They can click the link in the email to pay securely. "
                    "Thank them and wish them a great day."
                )
            )
            return

        if "dispute" in intent:
            self.hangup(
                final_instructions=(
                    f"Let {self.customer_name} know you've noted their dispute. "
                    "Our billing team will review and follow up by email within one business day. "
                    "Thank them for letting us know."
                )
            )
            return

        self.hangup(
            final_instructions=(
                f"Thank {self.customer_name} for their time and their commitment to pay invoice #{invoice_number}"
                + (f" for {amount_str}" if amount_str else "")
                + ". Let them know they can use the link in their invoice email to pay securely. "
                "Wish them a great day."
            )
        )

    def leave_voicemail(self):
        logging.info("Unable to reach %s for invoice collection.", self.customer_name)
        self.hangup(
            final_instructions=(
                f"Leave a professional voicemail for {self.customer_name} from Harbor Market. "
                f"Let them know you're calling about invoice {self.invoice_id} and ask them "
                "to check their email for the invoice link or call back. Keep it concise."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(description="Outbound Square invoice collection call.")
    parser.add_argument("phone", help="Customer phone number (E.164)")
    parser.add_argument("--name", required=True, help="Customer's full name")
    parser.add_argument("--invoice-id", required=True, help="Square invoice ID")
    args = parser.parse_args()

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=InvoiceCollectionController(
            customer_name=args.name,
            invoice_id=args.invoice_id,
        ),
    )

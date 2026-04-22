import guava
import os
import logging
from guava import logging_utils
import argparse
import requests
from datetime import datetime


STRIPE_SECRET_KEY = os.environ["STRIPE_SECRET_KEY"]
AUTH = (STRIPE_SECRET_KEY, "")
BASE_URL = "https://api.stripe.com"


def get_customer(customer_id: str) -> dict | None:
    resp = requests.get(f"{BASE_URL}/v1/customers/{customer_id}", auth=AUTH, timeout=10)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def list_open_invoices(customer_id: str) -> list:
    """Returns open (unpaid) invoices for the customer, most recent first."""
    resp = requests.get(
        f"{BASE_URL}/v1/invoices",
        auth=AUTH,
        params={"customer": customer_id, "status": "open", "limit": 5},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("data", [])


def pay_invoice(invoice_id: str) -> dict:
    """Attempts to collect payment on an open invoice using the customer's default payment method."""
    resp = requests.post(
        f"{BASE_URL}/v1/invoices/{invoice_id}/pay",
        auth=AUTH,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def format_amount(cents: int, currency: str = "usd") -> str:
    return f"${cents / 100:,.2f} {currency.upper()}"


class PaymentRecoveryController(guava.CallController):
    def __init__(self, customer_id: str, customer_name: str):
        super().__init__()
        self.customer_id = customer_id
        self.customer_name = customer_name
        self.invoices = []
        self.total_owed_str = ""

        try:
            self.invoices = list_open_invoices(customer_id)
            if self.invoices:
                total_cents = sum(inv.get("amount_due", 0) for inv in self.invoices)
                currency = self.invoices[0].get("currency", "usd")
                self.total_owed_str = format_amount(total_cents, currency)
        except Exception as e:
            logging.error("Failed to fetch invoices for %s pre-call: %s", customer_id, e)

        self.set_persona(
            organization_name="Luminary",
            agent_name="Casey",
            agent_purpose=(
                "to help Luminary customers resolve outstanding payment issues on their account"
            ),
        )

        self.reach_person(
            contact_full_name=self.customer_name,
            on_success=self.begin_recovery,
            on_failure=self.recipient_unavailable,
        )

    def begin_recovery(self):
        if not self.invoices:
            logging.info("No open invoices found for customer %s — call unnecessary", self.customer_id)
            self.hangup(
                final_instructions=(
                    f"Let {self.customer_name} know you're calling from Luminary about their account. "
                    "Upon review, it looks like their balance is actually clear. "
                    "Apologize for any confusion and wish them a great day."
                )
            )
            return

        invoice_count = len(self.invoices)
        amount_note = f" totaling {self.total_owed_str}" if self.total_owed_str else ""

        self.set_task(
            objective=(
                f"Reach {self.customer_name} about {invoice_count} outstanding "
                f"invoice{'s' if invoice_count > 1 else ''}{amount_note} on their Luminary account. "
                "Understand why payment failed and, if they've resolved the issue, retry the charge."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.customer_name}, this is Casey calling from Luminary. "
                    f"I'm reaching out because we noticed a payment issue on your account — "
                    f"there {'are' if invoice_count > 1 else 'is'} {invoice_count} outstanding "
                    f"invoice{'s' if invoice_count > 1 else ''}{amount_note} that we weren't "
                    "able to collect. I wanted to reach out personally to help get this sorted."
                ),
                guava.Field(
                    key="aware_of_issue",
                    field_type="multiple_choice",
                    description="Ask if they were aware of the payment issue.",
                    choices=["yes", "no"],
                    required=True,
                ),
                guava.Field(
                    key="cause",
                    field_type="multiple_choice",
                    description=(
                        "Ask what they think caused the payment failure. "
                        "Be empathetic — don't make them feel accused."
                    ),
                    choices=[
                        "card expired",
                        "card was replaced",
                        "insufficient funds",
                        "bank declined",
                        "not sure",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="updated_payment",
                    field_type="multiple_choice",
                    description=(
                        "Ask if they've already updated their payment method in their account, "
                        "or if they'd like us to retry the charge now."
                    ),
                    choices=[
                        "yes/updated my card, please retry",
                        "not yet/will update it",
                        "want to dispute the charge",
                    ],
                    required=True,
                ),
            ],
            on_complete=self.handle_outcome,
        )

    def handle_outcome(self):
        cause = self.get_field("cause") or "unknown"
        updated_payment = self.get_field("updated_payment") or ""

        logging.info(
            "Payment recovery outcome for %s — cause: %s, updated: %s",
            self.customer_id, cause, updated_payment,
        )

        if "retry" in updated_payment:
            # Attempt to pay all open invoices
            success_count = 0
            for invoice in self.invoices:
                try:
                    pay_invoice(invoice["id"])
                    success_count += 1
                    logging.info("Invoice %s paid successfully", invoice["id"])
                except Exception as e:
                    logging.error("Failed to pay invoice %s: %s", invoice["id"], e)

            if success_count == len(self.invoices):
                self.hangup(
                    final_instructions=(
                        f"Let {self.customer_name} know their payment was collected successfully — "
                        "their account is now fully up to date. "
                        "Thank them for resolving this so quickly and wish them a great day."
                    )
                )
            else:
                self.hangup(
                    final_instructions=(
                        f"Let {self.customer_name} know that the payment retry wasn't successful. "
                        "Ask them to log in and update their payment method, or call us back. "
                        "Assure them their account won't be affected immediately. "
                        "Thank them for their time."
                    )
                )
        elif "dispute" in updated_payment:
            self.hangup(
                final_instructions=(
                    f"Let {self.customer_name} know you've noted their dispute and a billing specialist "
                    "will review the charges and reach out by email within one business day. "
                    "Thank them for letting us know."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    f"Thank {self.customer_name} for their time. "
                    "Let them know they can update their payment method by logging into their account, "
                    "and once updated, we'll automatically retry the outstanding invoice. "
                    "Let them know we'll also send a reminder email with next steps. "
                    "Wish them a great day."
                )
            )

    def recipient_unavailable(self):
        logging.info("Unable to reach %s for payment recovery", self.customer_name)
        self.hangup(
            final_instructions=(
                f"Leave a brief, professional voicemail for {self.customer_name} on behalf of Luminary. "
                "Let them know you're calling about a payment issue on their account and ask them "
                "to log in to update their payment method, or call us back at their convenience. "
                "Keep it concise and non-threatening."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound payment recovery call for a Stripe customer with open invoices."
    )
    parser.add_argument("phone", help="Customer phone number (E.164, e.g. +15551234567)")
    parser.add_argument("--customer-id", required=True, help="Stripe customer ID (cus_...)")
    parser.add_argument("--name", required=True, help="Customer's full name")
    args = parser.parse_args()

    logging.info(
        "Initiating payment recovery call to %s (%s) for customer %s",
        args.name, args.phone, args.customer_id,
    )

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=PaymentRecoveryController(
            customer_id=args.customer_id,
            customer_name=args.name,
        ),
    )

import guava
import os
import logging
from guava import logging_utils
import requests
from datetime import datetime


BASE_URL = os.environ.get("SQUARE_BASE_URL", "https://connect.squareupsandbox.com")
SQUARE_VERSION = "2024-01-18"


def get_headers() -> dict:
    return {
        "Authorization": f"Bearer {os.environ['SQUARE_ACCESS_TOKEN']}",
        "Square-Version": SQUARE_VERSION,
        "Content-Type": "application/json",
    }


def search_payments(email: str) -> list:
    """Searches for recent payments by customer email via customer lookup + payments list."""
    headers = get_headers()
    # First search for the customer
    customer_resp = requests.post(
        f"{BASE_URL}/v2/customers/search",
        headers=headers,
        json={"query": {"filter": {"email_address": {"exact": email}}}},
        timeout=10,
    )
    if not customer_resp.ok:
        return []
    customers = customer_resp.json().get("customers", [])
    if not customers:
        return []

    customer_id = customers[0].get("id", "")

    # List recent payments for this customer
    payments_resp = requests.get(
        f"{BASE_URL}/v2/payments",
        headers=headers,
        params={"customer_id": customer_id, "limit": 5},
        timeout=10,
    )
    if not payments_resp.ok:
        return []
    return payments_resp.json().get("payments", [])


def format_amount(amount_money: dict) -> str:
    amount = amount_money.get("amount", 0)
    currency = amount_money.get("currency", "USD")
    return f"${amount / 100:,.2f} {currency}"


class PaymentInquiryController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Harbor Market",
            agent_name="Drew",
            agent_purpose="to help Harbor Market customers look up their recent Square payments",
        )

        self.set_task(
            objective=(
                "A customer has called about a recent payment. "
                "Verify their email and look up their most recent transactions."
            ),
            checklist=[
                guava.Say(
                    "Thanks for calling Harbor Market. This is Drew. "
                    "I can help you look up a recent payment today."
                ),
                guava.Field(
                    key="email",
                    field_type="text",
                    description="Ask for the email address associated with their purchase.",
                    required=True,
                ),
            ],
            on_complete=self.lookup_payments,
        )

        self.accept_call()

    def lookup_payments(self):
        email = (self.get_field("email") or "").strip().lower()
        logging.info("Searching Square payments for %s", email)

        try:
            payments = search_payments(email)
        except Exception as e:
            logging.error("Payment search failed: %s", e)
            payments = []

        if not payments:
            self.hangup(
                final_instructions=(
                    f"Let the caller know we couldn't find any recent payments linked to '{email}'. "
                    "Ask them to double-check the email or visit the store for help. "
                    "Be apologetic and helpful."
                )
            )
            return

        payment_summaries = []
        for p in payments[:3]:
            amount = p.get("amount_money", {})
            amount_str = format_amount(amount) if amount else ""
            status = p.get("status", "UNKNOWN")
            created = p.get("created_at", "")
            try:
                dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                date_str = dt.strftime("%B %-d")
            except (ValueError, AttributeError):
                date_str = created[:10] if created else "unknown date"
            payment_summaries.append(f"{amount_str} on {date_str} — {status.lower()}")

        logging.info("Found %d payments for %s", len(payments), email)

        self.hangup(
            final_instructions=(
                f"Let the caller know we found {len(payments)} recent payment(s) linked to their email. "
                f"The most recent are: {'; '.join(payment_summaries)}. "
                "Answer any questions they have about specific charges. "
                "If they want to dispute a charge or request a refund, let them know they can call back "
                "and we can process that for them. Be helpful and friendly."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=PaymentInquiryController,
    )

import guava
import os
import logging
import argparse
import requests
from datetime import datetime

logging.basicConfig(level=logging.INFO)

SITE = os.environ["CHARGEBEE_SITE"]
BASE_URL = f"https://{SITE}.chargebee.com/api/v2"
AUTH = (os.environ["CHARGEBEE_API_KEY"], "")


def get_subscription(subscription_id: str) -> dict | None:
    resp = requests.get(f"{BASE_URL}/subscriptions/{subscription_id}", auth=AUTH, timeout=10)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json().get("subscription")


def list_unbilled_charges(subscription_id: str) -> list:
    resp = requests.get(
        f"{BASE_URL}/unbilled_charges",
        auth=AUTH,
        params={"subscription_id[is]": subscription_id},
        timeout=10,
    )
    if not resp.ok:
        return []
    return [entry.get("unbilled_charge") for entry in resp.json().get("list", []) if entry.get("unbilled_charge")]


def collect_now(subscription_id: str) -> bool:
    """Triggers immediate payment collection on a dunning subscription."""
    resp = requests.post(
        f"{BASE_URL}/subscriptions/{subscription_id}/collect_now",
        auth=AUTH,
        timeout=15,
    )
    return resp.ok


def format_amount(cents: int, currency: str = "USD") -> str:
    return f"${cents / 100:,.2f} {currency.upper()}"


class PaymentRecoveryController(guava.CallController):
    def __init__(self, customer_name: str, subscription_id: str):
        super().__init__()
        self.customer_name = customer_name
        self.subscription_id = subscription_id
        self.subscription = None
        self.total_owed_str = ""

        try:
            self.subscription = get_subscription(subscription_id)
            if self.subscription:
                due_invoices = self.subscription.get("due_invoices_count", 0)
                due_since = self.subscription.get("due_since")
                total_dues = self.subscription.get("total_dues", 0)
                currency = self.subscription.get("currency_code", "USD")
                if total_dues:
                    self.total_owed_str = format_amount(total_dues, currency)
        except Exception as e:
            logging.error("Failed to load subscription %s: %s", subscription_id, e)

        self.set_persona(
            organization_name="Vault",
            agent_name="Riley",
            agent_purpose="to help Vault customers resolve outstanding payment issues",
        )

        self.reach_person(
            contact_full_name=self.customer_name,
            on_success=self.begin_recovery,
            on_failure=self.leave_voicemail,
        )

    def begin_recovery(self):
        amount_note = f" totaling {self.total_owed_str}" if self.total_owed_str else ""

        self.set_task(
            objective=(
                f"Reach {self.customer_name} about a payment issue on their Vault subscription{amount_note}. "
                "Understand why payment failed and retry if they've updated their payment method."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.customer_name}, this is Riley calling from Vault. "
                    f"I'm reaching out because we had a payment issue on your subscription"
                    + (f" — there's an outstanding balance of {self.total_owed_str}" if self.total_owed_str else "")
                    + ". I wanted to connect personally to help get this sorted quickly."
                ),
                guava.Field(
                    key="aware",
                    field_type="multiple_choice",
                    description="Ask if they were aware of the payment issue.",
                    choices=["yes", "no"],
                    required=True,
                ),
                guava.Field(
                    key="cause",
                    field_type="multiple_choice",
                    description="Ask what they think caused the failure.",
                    choices=["card expired", "card was replaced", "insufficient funds", "bank declined", "not sure"],
                    required=True,
                ),
                guava.Field(
                    key="updated_payment",
                    field_type="multiple_choice",
                    description=(
                        "Ask if they've updated their payment method in their Vault account, "
                        "or if they'd like us to retry the charge now."
                    ),
                    choices=["yes, updated — please retry", "not yet", "want to cancel"],
                    required=True,
                ),
            ],
            on_complete=self.handle_outcome,
        )

    def handle_outcome(self):
        cause = self.get_field("cause") or ""
        updated = self.get_field("updated_payment") or ""

        logging.info(
            "Payment recovery for subscription %s — cause: %s, updated: %s",
            self.subscription_id, cause, updated,
        )

        if "cancel" in updated:
            self.hangup(
                final_instructions=(
                    f"Acknowledge {self.customer_name}'s wish to cancel. Let them know they can cancel "
                    "by logging into their Vault account or calling back. Thank them for being a customer."
                )
            )
            return

        if "retry" in updated:
            success = False
            try:
                success = collect_now(self.subscription_id)
                logging.info("Collect now result for %s: %s", self.subscription_id, success)
            except Exception as e:
                logging.error("Collect now failed: %s", e)

            if success:
                self.hangup(
                    final_instructions=(
                        f"Let {self.customer_name} know the payment was collected successfully — "
                        "their account is now fully up to date. "
                        "Thank them for resolving this quickly and wish them a great day."
                    )
                )
            else:
                self.hangup(
                    final_instructions=(
                        f"Let {self.customer_name} know the payment retry wasn't successful. "
                        "Ask them to log into their Vault account and update their payment method — "
                        "we'll retry automatically once it's updated. Thank them for their patience."
                    )
                )
        else:
            self.hangup(
                final_instructions=(
                    f"Thank {self.customer_name} for their time. Let them know they can update their "
                    "payment method by logging into their Vault account, and we'll retry the charge automatically. "
                    "We'll also send a reminder email. Wish them a great day."
                )
            )

    def leave_voicemail(self):
        logging.info("Unable to reach %s for payment recovery.", self.customer_name)
        self.hangup(
            final_instructions=(
                f"Leave a brief voicemail for {self.customer_name} from Vault. "
                "Let them know you're calling about a payment issue on their account and ask them "
                "to log in and update their payment method, or call us back. "
                "Keep it professional and non-threatening."
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Outbound Chargebee payment recovery call.")
    parser.add_argument("phone", help="Customer phone number (E.164)")
    parser.add_argument("--name", required=True)
    parser.add_argument("--subscription-id", required=True)
    args = parser.parse_args()

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=PaymentRecoveryController(
            customer_name=args.name,
            subscription_id=args.subscription_id,
        ),
    )

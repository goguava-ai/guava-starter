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


def end_trial_now(subscription_id: str) -> dict | None:
    """Ends the trial immediately, converting the subscription to paid."""
    resp = requests.post(
        f"{BASE_URL}/subscriptions/{subscription_id}/change_term_end",
        auth=AUTH,
        data={"term_ends_at": str(int(datetime.utcnow().timestamp())), "prorate": "false"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("subscription")


def format_date(unix_ts: int) -> str:
    return datetime.utcfromtimestamp(unix_ts).strftime("%B %d, %Y")


def format_amount(cents: int, currency: str = "USD") -> str:
    return f"${cents / 100:,.2f} {currency.upper()}"


class TrialConversionController(guava.CallController):
    def __init__(self, customer_name: str, subscription_id: str, trial_end: str):
        super().__init__()
        self.customer_name = customer_name
        self.subscription_id = subscription_id
        self.trial_end = trial_end
        self.subscription = None

        try:
            self.subscription = get_subscription(subscription_id)
        except Exception as e:
            logging.error("Failed to load subscription %s: %s", subscription_id, e)

        plan_name = ""
        amount_str = ""
        period = "month"
        if self.subscription:
            plan_name = self.subscription.get("plan_id", "")
            plan_amount = self.subscription.get("plan_amount", 0)
            currency = self.subscription.get("currency_code", "USD")
            period = self.subscription.get("billing_period_unit", "month")
            if plan_amount:
                amount_str = format_amount(plan_amount, currency)

        self.set_persona(
            organization_name="Vault",
            agent_name="Riley",
            agent_purpose=(
                "to help Vault trial users understand the value of converting to a paid plan"
            ),
        )

        self.set_task(
            objective=(
                f"Call {customer_name} whose trial ends on {trial_end}. "
                "Understand their experience, address concerns, and offer to convert them to paid."
            ),
            checklist=[
                guava.Say(
                    f"Hi {customer_name}, this is Riley from Vault. "
                    f"I'm reaching out because your free trial is coming to an end on {trial_end}. "
                    "I just wanted to check in and see how things are going with the product."
                ),
                guava.Field(
                    key="experience",
                    field_type="multiple_choice",
                    description="Ask how their trial experience has been.",
                    choices=["great, loving it", "good, some questions", "mixed, have concerns", "not using it much"],
                    required=True,
                ),
                guava.Field(
                    key="main_concern",
                    field_type="text",
                    description=(
                        "Ask if they have any specific concerns or questions about converting to paid. "
                        "This could be about pricing, features, or next steps."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="ready_to_convert",
                    field_type="multiple_choice",
                    description=(
                        f"Ask if they'd like to convert to the paid plan now"
                        + (f" at {amount_str}/{period}" if amount_str else "")
                        + ". We can activate it immediately so there's no interruption in access."
                    ),
                    choices=["yes, convert now", "need more time to decide", "no, let trial expire"],
                    required=True,
                ),
            ],
            on_complete=self.handle_conversion,
        )

        self.reach_person(
            contact_full_name=self.customer_name,
            on_success=lambda: None,
            on_failure=self.leave_voicemail,
        )

    def handle_conversion(self):
        experience = self.get_field("experience") or ""
        concern = self.get_field("main_concern") or ""
        ready = self.get_field("ready_to_convert") or ""

        logging.info(
            "Trial conversion for %s — experience: %s, ready: %s",
            self.subscription_id, experience, ready,
        )

        if "yes" in ready or "convert" in ready:
            converted = None
            try:
                converted = end_trial_now(self.subscription_id)
                logging.info("Trial ended immediately for %s: %s", self.subscription_id, bool(converted))
            except Exception as e:
                logging.error("Trial conversion failed: %s", e)

            if converted:
                self.hangup(
                    final_instructions=(
                        f"Let {self.customer_name} know their Vault subscription is now active — "
                        "the trial has been converted and they have full access with no interruption. "
                        "They'll receive a confirmation and first invoice by email. "
                        "Thank them for choosing Vault and wish them a great day."
                    )
                )
            else:
                self.hangup(
                    final_instructions=(
                        f"Apologize to {self.customer_name} — the conversion couldn't be processed automatically. "
                        "Let them know our team will complete the activation by end of day "
                        "and they'll receive a confirmation email. Thank them for their patience."
                    )
                )
        elif "more time" in ready:
            self.hangup(
                final_instructions=(
                    f"Thank {self.customer_name} for their time. Let them know their trial will "
                    f"remain active until {self.trial_end}. They can convert anytime by logging "
                    "into their Vault account or calling back. Wish them a great day."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    f"Respect {self.customer_name}'s decision. Let them know their access will end on {self.trial_end}. "
                    "Invite them to come back and sign up anytime. Thank them for trying Vault."
                )
            )

    def leave_voicemail(self):
        logging.info("Unable to reach %s for trial conversion.", self.customer_name)
        self.hangup(
            final_instructions=(
                f"Leave a brief, warm voicemail for {self.customer_name} from Vault. "
                f"Let them know their trial ends on {self.trial_end} and you wanted to check in. "
                "Invite them to call back or log into their account to convert or ask any questions. "
                "Keep it friendly — not pushy."
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Outbound Chargebee trial conversion call.")
    parser.add_argument("phone", help="Customer phone number (E.164)")
    parser.add_argument("--name", required=True)
    parser.add_argument("--subscription-id", required=True)
    parser.add_argument("--trial-end", required=True, help="Trial end date (display string, e.g. 'March 30, 2026')")
    args = parser.parse_args()

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=TrialConversionController(
            customer_name=args.name,
            subscription_id=args.subscription_id,
            trial_end=args.trial_end,
        ),
    )

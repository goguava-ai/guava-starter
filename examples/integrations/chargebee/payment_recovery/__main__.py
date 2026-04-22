import guava
import os
import logging
from guava import logging_utils
import argparse
import requests
from datetime import datetime


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


agent = guava.Agent(
    name="Riley",
    organization="Vault",
    purpose="to help Vault customers resolve outstanding payment issues",
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    subscription_id = call.get_variable("subscription_id")

    subscription = None
    total_owed_str = ""
    try:
        subscription = get_subscription(subscription_id)
        if subscription:
            total_dues = subscription.get("total_dues", 0)
            currency = subscription.get("currency_code", "USD")
            if total_dues:
                total_owed_str = format_amount(total_dues, currency)
    except Exception as e:
        logging.error("Failed to load subscription %s: %s", subscription_id, e)

    call.set_variable("total_owed_str", total_owed_str)
    call.reach_person(contact_full_name=customer_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    customer_name = call.get_variable("customer_name")
    if outcome == "unavailable":
        logging.info("Unable to reach %s for payment recovery.", customer_name)
        call.hangup(
            final_instructions=(
                f"Leave a brief voicemail for {customer_name} from Vault. "
                "Let them know you're calling about a payment issue on their account and ask them "
                "to log in and update their payment method, or call us back. "
                "Keep it professional and non-threatening."
            )
        )
    elif outcome == "available":
        total_owed_str = call.get_variable("total_owed_str") or ""
        amount_note = f" totaling {total_owed_str}" if total_owed_str else ""

        call.set_task(
            "handle_outcome",
            objective=(
                f"Reach {customer_name} about a payment issue on their Vault subscription{amount_note}. "
                "Understand why payment failed and retry if they've updated their payment method."
            ),
            checklist=[
                guava.Say(
                    f"Hi {customer_name}, this is Riley calling from Vault. "
                    f"I'm reaching out because we had a payment issue on your subscription"
                    + (f" — there's an outstanding balance of {total_owed_str}" if total_owed_str else "")
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
        )


@agent.on_task_complete("handle_outcome")
def on_handle_outcome(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    subscription_id = call.get_variable("subscription_id")
    cause = call.get_field("cause") or ""
    updated = call.get_field("updated_payment") or ""

    logging.info(
        "Payment recovery for subscription %s — cause: %s, updated: %s",
        subscription_id, cause, updated,
    )

    if "cancel" in updated:
        call.hangup(
            final_instructions=(
                f"Acknowledge {customer_name}'s wish to cancel. Let them know they can cancel "
                "by logging into their Vault account or calling back. Thank them for being a customer."
            )
        )
        return

    if "retry" in updated:
        success = False
        try:
            success = collect_now(subscription_id)
            logging.info("Collect now result for %s: %s", subscription_id, success)
        except Exception as e:
            logging.error("Collect now failed: %s", e)

        if success:
            call.hangup(
                final_instructions=(
                    f"Let {customer_name} know the payment was collected successfully — "
                    "their account is now fully up to date. "
                    "Thank them for resolving this quickly and wish them a great day."
                )
            )
        else:
            call.hangup(
                final_instructions=(
                    f"Let {customer_name} know the payment retry wasn't successful. "
                    "Ask them to log into their Vault account and update their payment method — "
                    "we'll retry automatically once it's updated. Thank them for their patience."
                )
            )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {customer_name} for their time. Let them know they can update their "
                "payment method by logging into their Vault account, and we'll retry the charge automatically. "
                "We'll also send a reminder email. Wish them a great day."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(description="Outbound Chargebee payment recovery call.")
    parser.add_argument("phone", help="Customer phone number (E.164)")
    parser.add_argument("--name", required=True)
    parser.add_argument("--subscription-id", required=True)
    args = parser.parse_args()

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "customer_name": args.name,
            "subscription_id": args.subscription_id,
        },
    )

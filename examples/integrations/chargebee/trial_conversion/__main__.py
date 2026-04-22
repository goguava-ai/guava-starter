import argparse
import logging
import os
from datetime import datetime, timezone

import guava
import requests
from guava import logging_utils

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
        data={"term_ends_at": str(int(datetime.now(timezone.utc).timestamp())), "prorate": "false"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("subscription")


def format_date(unix_ts: int) -> str:
    return datetime.fromtimestamp(unix_ts, tz=timezone.utc).strftime("%B %d, %Y")


def format_amount(cents: int, currency: str = "USD") -> str:
    return f"${cents / 100:,.2f} {currency.upper()}"


agent = guava.Agent(
    name="Riley",
    organization="Vault",
    purpose=(
        "to help Vault trial users understand the value of converting to a paid plan"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    subscription_id = call.get_variable("subscription_id")
    trial_end = call.get_variable("trial_end")

    subscription = None
    try:
        subscription = get_subscription(subscription_id)
    except Exception as e:
        logging.error("Failed to load subscription %s: %s", subscription_id, e)

    amount_str = ""
    period = "month"
    if subscription:
        plan_amount = subscription.get("plan_amount", 0)
        currency = subscription.get("currency_code", "USD")
        period = subscription.get("billing_period_unit", "month")
        if plan_amount:
            amount_str = format_amount(plan_amount, currency)

    call.set_variable("amount_str", amount_str)
    call.set_variable("period", period)
    call.reach_person(contact_full_name=customer_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    customer_name = call.get_variable("customer_name")
    trial_end = call.get_variable("trial_end")
    if outcome == "unavailable":
        logging.info("Unable to reach %s for trial conversion.", customer_name)
        call.hangup(
            final_instructions=(
                f"Leave a brief, warm voicemail for {customer_name} from Vault. "
                f"Let them know their trial ends on {trial_end} and you wanted to check in. "
                "Invite them to call back or log into their account to convert or ask any questions. "
                "Keep it friendly — not pushy."
            )
        )
    elif outcome == "available":
        amount_str = call.get_variable("amount_str") or ""
        period = call.get_variable("period") or "month"
        call.set_task(
            "handle_conversion",
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
        )


@agent.on_task_complete("handle_conversion")
def on_handle_conversion(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    subscription_id = call.get_variable("subscription_id")
    trial_end = call.get_variable("trial_end")
    experience = call.get_field("experience") or ""
    concern = call.get_field("main_concern") or ""
    ready = call.get_field("ready_to_convert") or ""

    logging.info(
        "Trial conversion for %s — experience: %s, ready: %s",
        subscription_id, experience, ready,
    )

    if "yes" in ready or "convert" in ready:
        converted = None
        try:
            converted = end_trial_now(subscription_id)
            logging.info("Trial ended immediately for %s: %s", subscription_id, bool(converted))
        except Exception as e:
            logging.error("Trial conversion failed: %s", e)

        if converted:
            call.hangup(
                final_instructions=(
                    f"Let {customer_name} know their Vault subscription is now active — "
                    "the trial has been converted and they have full access with no interruption. "
                    "They'll receive a confirmation and first invoice by email. "
                    "Thank them for choosing Vault and wish them a great day."
                )
            )
        else:
            call.hangup(
                final_instructions=(
                    f"Apologize to {customer_name} — the conversion couldn't be processed automatically. "
                    "Let them know our team will complete the activation by end of day "
                    "and they'll receive a confirmation email. Thank them for their patience."
                )
            )
    elif "more time" in ready:
        call.hangup(
            final_instructions=(
                f"Thank {customer_name} for their time. Let them know their trial will "
                f"remain active until {trial_end}. They can convert anytime by logging "
                "into their Vault account or calling back. Wish them a great day."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Respect {customer_name}'s decision. Let them know their access will end on {trial_end}. "
                "Invite them to come back and sign up anytime. Thank them for trying Vault."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(description="Outbound Chargebee trial conversion call.")
    parser.add_argument("phone", help="Customer phone number (E.164)")
    parser.add_argument("--name", required=True)
    parser.add_argument("--subscription-id", required=True)
    parser.add_argument("--trial-end", required=True, help="Trial end date (display string, e.g. 'March 30, 2026')")
    args = parser.parse_args()

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "customer_name": args.name,
            "subscription_id": args.subscription_id,
            "trial_end": args.trial_end,
        },
    )

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
    resp = requests.get(
        f"{BASE_URL}/subscriptions/{subscription_id}",
        auth=AUTH,
        timeout=10,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json().get("subscription")


def get_customer(customer_id: str) -> dict | None:
    resp = requests.get(f"{BASE_URL}/customers/{customer_id}", auth=AUTH, timeout=10)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json().get("customer")


def format_amount(cents: int, currency: str = "USD") -> str:
    return f"${cents / 100:,.2f} {currency.upper()}"


def format_date(unix_ts: int) -> str:
    return datetime.fromtimestamp(unix_ts, tz=timezone.utc).strftime("%B %d, %Y")


agent = guava.Agent(
    name="Riley",
    organization="Vault",
    purpose=(
        "to help Vault customers look up their subscription details and answer billing questions"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "lookup_subscription",
        objective=(
            "A customer has called about their Vault subscription. "
            "Verify their identity via email and look up their subscription details."
        ),
        checklist=[
            guava.Say(
                "Thanks for calling Vault. This is Riley. "
                "I can help you with questions about your subscription today."
            ),
            guava.Field(
                key="email",
                field_type="text",
                description="Ask for the email address on their Vault account.",
                required=True,
            ),
            guava.Field(
                key="subscription_id",
                field_type="text",
                description=(
                    "Ask for their subscription ID. "
                    "They can find it in any billing confirmation email from Vault."
                ),
                required=True,
            ),
        ],
    )


@agent.on_task_complete("lookup_subscription")
def on_lookup_subscription(call: guava.Call) -> None:
    email = call.get_field("email") or ""
    subscription_id = (call.get_field("subscription_id") or "").strip()

    logging.info("Looking up Chargebee subscription %s for %s", subscription_id, email)

    try:
        sub = get_subscription(subscription_id)
    except Exception as e:
        logging.error("Subscription lookup failed: %s", e)
        sub = None

    if not sub:
        call.hangup(
            final_instructions=(
                f"Let the caller know we couldn't find a subscription with ID '{subscription_id}'. "
                "Ask them to check their billing email for the correct ID. Be apologetic and helpful."
            )
        )
        return

    status = sub.get("status", "unknown")
    plan_id = sub.get("plan_id", "")
    plan_amount = sub.get("plan_amount", 0)
    currency = sub.get("currency_code", "USD")
    billing_period = sub.get("billing_period_unit", "month")
    current_term_end = sub.get("current_term_end")
    cancel_at_end = sub.get("cancel_at_end", False)
    customer_id = sub.get("customer_id", "")

    name = ""
    try:
        customer = get_customer(customer_id)
        if customer:
            name = customer.get("first_name", "")
    except Exception:
        pass

    amount_str = format_amount(plan_amount, currency) if plan_amount else ""
    renewal_str = format_date(current_term_end) if current_term_end else "unknown"

    cancel_note = (
        f" Note: the subscription is scheduled to cancel on {renewal_str}."
        if cancel_at_end else ""
    )

    logging.info("Subscription %s: plan=%s, status=%s", subscription_id, plan_id, status)

    call.hangup(
        final_instructions=(
            f"{'Greet ' + name + ' by name. ' if name else ''}"
            f"Their subscription details: plan is '{plan_id}', status is {status}, "
            + (f"billing amount is {amount_str}/{billing_period}, " if amount_str else "")
            + f"and the {'cancellation' if cancel_at_end else 'next renewal'} date is {renewal_str}.{cancel_note} "
            "Answer any questions they have using this information. "
            "If they want to make changes — cancel, upgrade, or request a refund — "
            "let them know they can call back and we'll assist. Be friendly and thorough."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])

import guava
import os
import logging
from guava import logging_utils
import requests
from datetime import datetime, timezone


STRIPE_SECRET_KEY = os.environ["STRIPE_SECRET_KEY"]
AUTH = (STRIPE_SECRET_KEY, "")
BASE_URL = "https://api.stripe.com"


def search_customer_by_email(email: str) -> dict | None:
    """Searches Stripe for a customer by email. Returns the customer or None."""
    resp = requests.get(
        f"{BASE_URL}/v1/customers/search",
        auth=AUTH,
        params={"query": f'email:"{email}"', "limit": 1},
        timeout=10,
    )
    resp.raise_for_status()
    results = resp.json().get("data", [])
    return results[0] if results else None


def list_subscriptions(customer_id: str, status: str = "active") -> list:
    resp = requests.get(
        f"{BASE_URL}/v1/subscriptions",
        auth=AUTH,
        params={"customer": customer_id, "status": status, "limit": 5},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("data", [])


def format_amount(cents: int, currency: str = "usd") -> str:
    return f"${cents / 100:,.2f} {currency.upper()}"


def format_date(unix_ts: int) -> str:
    return datetime.fromtimestamp(unix_ts, tz=timezone.utc).strftime("%B %d, %Y")


agent = guava.Agent(
    name="Riley",
    organization="Luminary",
    purpose=(
        "to help Luminary customers look up their subscription details "
        "and answer billing questions"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "lookup_and_respond",
        objective=(
            "An existing customer has called to check on their subscription. "
            "Verify their identity via email, look up their Stripe subscription, "
            "and answer any questions about their plan, billing amount, or renewal date."
        ),
        checklist=[
            guava.Say(
                "Thanks for calling Luminary. I'm Riley, and I can help you with "
                "questions about your subscription. Let me pull up your account."
            ),
            guava.Field(
                key="caller_email",
                field_type="text",
                description="Ask for their email address on file.",
                required=True,
            ),
        ],
    )


@agent.on_task_complete("lookup_and_respond")
def lookup_and_respond(call: guava.Call) -> None:
    email = call.get_field("caller_email") or ""
    logging.info("Looking up Stripe customer for email: %s", email)

    try:
        customer = search_customer_by_email(email)
    except Exception as e:
        logging.error("Stripe customer search failed for %s: %s", email, e)
        customer = None

    if not customer:
        call.hangup(
            final_instructions=(
                "Let the caller know you couldn't find an account with that email. "
                "Ask them to double-check or offer to transfer them to a live agent. "
                "Be apologetic and helpful."
            )
        )
        return

    customer_id = customer["id"]
    name = customer.get("name") or "there"

    try:
        subscriptions = list_subscriptions(customer_id, status="active")
        # Also check trialing
        if not subscriptions:
            subscriptions = list_subscriptions(customer_id, status="trialing")
        # Check past_due
        if not subscriptions:
            subscriptions = list_subscriptions(customer_id, status="past_due")
    except Exception as e:
        logging.error("Failed to list subscriptions for %s: %s", customer_id, e)
        subscriptions = []

    if not subscriptions:
        call.hangup(
            final_instructions=(
                f"Greet {name} by name. Let them know there is no active subscription "
                "linked to their account. If they believe this is an error, offer to "
                "transfer them to a billing specialist. Be helpful and apologetic."
            )
        )
        return

    sub = subscriptions[0]
    status = sub.get("status", "unknown")
    cancel_at_period_end = sub.get("cancel_at_period_end", False)
    current_period_end = sub.get("current_period_end")
    items = sub.get("items", {}).get("data", [])

    plan_name = "your current plan"
    amount_str = ""
    interval = ""

    if items:
        price = items[0].get("price", {})
        plan_name = price.get("nickname") or price.get("id") or "your current plan"
        unit_amount = price.get("unit_amount")
        currency = price.get("currency", "usd")
        interval = price.get("recurring", {}).get("interval", "month")
        if unit_amount is not None:
            amount_str = f"{format_amount(unit_amount, currency)}/{interval}"

    renewal_date = format_date(current_period_end) if current_period_end else "unknown"

    cancellation_note = ""
    if cancel_at_period_end:
        cancellation_note = (
            f" Note: their subscription is set to cancel on {renewal_date} "
            "and will not renew."
        )

    logging.info(
        "Subscription found for %s: plan=%s, status=%s, renews=%s",
        customer_id, plan_name, status, renewal_date,
    )

    call.hangup(
        final_instructions=(
            f"Greet {name} by name. "
            f"Their subscription details: plan is '{plan_name}', "
            f"status is {status}, "
            + (f"billing amount is {amount_str}, " if amount_str else "")
            + f"and the {'cancellation' if cancel_at_period_end else 'next renewal'} date is {renewal_date}. "
            + cancellation_note
            + " Answer any questions they have using this information. "
            "If they want to make changes, let them know they can call back and say they want to "
            "cancel, upgrade, or request a refund and we can help. Be friendly and thorough."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])

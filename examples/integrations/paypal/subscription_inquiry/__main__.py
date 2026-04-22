import guava
import os
import logging
from guava import logging_utils
import requests
from datetime import datetime


BASE_URL = os.environ.get("PAYPAL_BASE_URL", "https://api-m.sandbox.paypal.com")


def get_access_token() -> str:
    resp = requests.post(
        f"{BASE_URL}/v1/oauth2/token",
        data={"grant_type": "client_credentials"},
        auth=(os.environ["PAYPAL_CLIENT_ID"], os.environ["PAYPAL_CLIENT_SECRET"]),
        headers={"Accept": "application/json"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def get_subscription(subscription_id: str, headers: dict) -> dict | None:
    resp = requests.get(
        f"{BASE_URL}/v1/billing/subscriptions/{subscription_id}",
        headers=headers,
        timeout=10,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def format_date(iso_str: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%B %-d, %Y")
    except (ValueError, AttributeError):
        return iso_str


agent = guava.Agent(
    name="Alex",
    organization="Northgate Commerce",
    purpose="to help Northgate Commerce customers check on their PayPal subscription",
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "lookup_subscription",
        objective=(
            "A customer has called about their subscription. Collect their subscription ID "
            "and answer questions about plan, billing amount, and next payment date."
        ),
        checklist=[
            guava.Say(
                "Thanks for calling Northgate Commerce. This is Alex. "
                "I can help you with your subscription today."
            ),
            guava.Field(
                key="email",
                field_type="text",
                description="Ask for the email address on their account.",
                required=True,
            ),
            guava.Field(
                key="subscription_id",
                field_type="text",
                description=(
                    "Ask for their PayPal subscription ID. "
                    "It starts with 'I-' and can be found in their subscription confirmation email."
                ),
                required=True,
            ),
        ],
    )


@agent.on_task_complete("lookup_subscription")
def on_done(call: guava.Call) -> None:
    subscription_id = (call.get_field("subscription_id") or "").strip()
    email = call.get_field("email") or ""

    logging.info("Looking up PayPal subscription %s for %s", subscription_id, email)

    try:
        token = get_access_token()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        sub = get_subscription(subscription_id, headers)
    except Exception as e:
        logging.error("Subscription lookup failed: %s", e)
        sub = None

    if not sub:
        call.hangup(
            final_instructions=(
                f"Let the caller know we couldn't find a subscription with ID '{subscription_id}'. "
                "Ask them to check the ID from their subscription email. "
                "They can also log into PayPal to view their subscriptions. Be helpful."
            )
        )
        return

    status = sub.get("status", "UNKNOWN")
    plan_id = sub.get("plan_id", "")
    next_billing = sub.get("billing_info", {}).get("next_billing_time", "")
    last_amount = sub.get("billing_info", {}).get("last_payment", {}).get("amount", {})
    amount_str = f"${last_amount.get('value', '')} {last_amount.get('currency_code', 'USD')}" if last_amount.get("value") else ""
    next_date = format_date(next_billing) if next_billing else "unknown"

    failed_payments = sub.get("billing_info", {}).get("failed_payments_count", 0)
    failure_note = f" There have been {failed_payments} failed payment(s) on this subscription." if failed_payments else ""

    logging.info("Subscription %s: status=%s, next=%s", subscription_id, status, next_billing)

    call.hangup(
        final_instructions=(
            f"Let the caller know their PayPal subscription (ID: {subscription_id}) has a status of {status.lower()}. "
            + (f"The plan ID is {plan_id}. " if plan_id else "")
            + (f"Their last payment amount was {amount_str}. " if amount_str else "")
            + f"The next billing date is {next_date}.{failure_note} "
            "If they want to cancel or update their subscription, they can do so through PayPal. "
            "Answer any other questions they have. Be thorough and friendly."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])

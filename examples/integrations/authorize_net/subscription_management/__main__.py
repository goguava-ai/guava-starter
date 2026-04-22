import guava
import os
import logging
from guava import logging_utils
import requests
from datetime import datetime, timedelta, timezone


API_LOGIN_ID = os.environ["AUTHNET_API_LOGIN_ID"]
TRANSACTION_KEY = os.environ["AUTHNET_TRANSACTION_KEY"]
BASE_URL = (
    "https://api.authorize.net/xml/v1/request.api"
    if os.environ.get("AUTHNET_ENVIRONMENT") == "production"
    else "https://apitest.authorize.net/xml/v1/request.api"
)


def authnet_credentials() -> dict:
    return {"name": API_LOGIN_ID, "transactionKey": TRANSACTION_KEY}


def api_call(payload: dict) -> dict:
    resp = requests.post(BASE_URL, json=payload, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    messages = data.get("messages", {})
    if messages.get("resultCode") == "Error":
        raise RuntimeError(
            f"Authorize.net error: {messages.get('message', [{}])[0].get('text', 'Unknown error')}"
        )
    return data


def get_subscription(subscription_id: str) -> dict:
    payload = {
        "ARBGetSubscriptionRequest": {
            "merchantAuthentication": authnet_credentials(),
            "subscriptionId": subscription_id,
        }
    }
    return api_call(payload)


def cancel_subscription(subscription_id: str) -> dict:
    payload = {
        "ARBCancelSubscriptionRequest": {
            "merchantAuthentication": authnet_credentials(),
            "subscriptionId": subscription_id,
        }
    }
    return api_call(payload)


def estimate_next_billing_date(start_date_str: str, interval_length: int, interval_unit: str) -> str:
    """
    Given the subscription start date and billing interval, estimate the next billing date
    by computing the most recent cycle past today and adding one interval.
    """
    try:
        start = datetime.strptime(start_date_str[:10], "%Y-%m-%d")
        today = datetime.now(timezone.utc)
        if interval_unit == "months":
            # Approximate: advance month by month
            current = start
            while current <= today:
                month = current.month + interval_length
                year = current.year + (month - 1) // 12
                month = (month - 1) % 12 + 1
                current = current.replace(year=year, month=month)
            return current.strftime("%B %d, %Y")
        elif interval_unit == "days":
            delta = timedelta(days=interval_length)
            current = start
            while current <= today:
                current += delta
            return current.strftime("%B %d, %Y")
        else:
            return "unknown"
    except Exception:
        return "unknown"


agent = guava.Agent(
    name="Riley",
    organization="Pinnacle Payments",
    purpose=(
        "to help Pinnacle Payments customers manage their recurring subscriptions"
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
            "A customer has called to manage their recurring subscription. "
            "Collect their email and subscription ID, look up the subscription, "
            "read back the details, and help them take action."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling Pinnacle Payments. I'm Riley, and I can help you "
                "with your recurring subscription today."
            ),
            guava.Field(
                key="email",
                field_type="text",
                description="Ask for the customer's email address on file.",
                required=True,
            ),
            guava.Field(
                key="subscription_id",
                field_type="text",
                description=(
                    "Ask for their subscription ID from their confirmation email."
                ),
                required=True,
            ),
        ],
    )


@agent.on_task_complete("lookup_subscription")
def on_lookup_subscription_done(call: guava.Call) -> None:
    email = call.get_field("email") or ""
    subscription_id = (call.get_field("subscription_id") or "").strip()

    logging.info(
        "Subscription lookup — email: %s, subscriptionId: %s", email, subscription_id
    )

    try:
        data = get_subscription(subscription_id)
        sub = data.get("subscription", {})
    except Exception as e:
        logging.error("Failed to fetch subscription %s: %s", subscription_id, e)
        call.hangup(
            final_instructions=(
                "Apologize and let the caller know you couldn't retrieve their subscription details. "
                "Ask them to double-check their subscription ID or offer to connect them with "
                "a billing specialist. Be helpful and empathetic."
            )
        )
        return

    if not sub:
        call.hangup(
            final_instructions=(
                "Let the caller know no subscription was found for that ID. "
                "Ask them to verify the subscription ID from their confirmation email. "
                "Offer to connect them with a billing specialist if needed."
            )
        )
        return

    call.set_variable("subscription", sub)
    call.set_variable("subscription_id", subscription_id)

    # Parse subscription details
    plan_name = sub.get("name", "your subscription")
    amount = sub.get("amount", "")
    amount_str = f"${float(amount):,.2f}" if amount else "an unknown amount"
    status = sub.get("status", "unknown")

    schedule = sub.get("paymentSchedule", {})
    interval = schedule.get("interval", {})
    interval_length = interval.get("length", 1)
    interval_unit = interval.get("unit", "months")
    start_date = schedule.get("startDate", "")

    next_billing = estimate_next_billing_date(start_date, interval_length, interval_unit)
    billing_interval_str = f"every {interval_length} {interval_unit}"

    logging.info(
        "Subscription %s — plan: %s, status: %s, amount: %s, interval: %s",
        subscription_id, plan_name, status, amount, billing_interval_str,
    )

    call.set_task(
        "manage_subscription",
        objective=(
            f"You've retrieved the subscription details. Read them back to the customer "
            f"and ask what they'd like to do."
        ),
        checklist=[
            guava.Say(
                f"I found your subscription. Here are the details: "
                f"Plan name: {plan_name}. "
                f"Billing amount: {amount_str} {billing_interval_str}. "
                f"Status: {status}. "
                f"Next billing date: {next_billing}."
            ),
            guava.Field(
                key="desired_action",
                field_type="multiple_choice",
                description="Ask what they would like to do with their subscription.",
                choices=[
                    "cancel my subscription",
                    "pause my subscription",
                    "check billing date",
                    "update payment method",
                    "nothing, just checking",
                ],
                required=True,
            ),
        ],
    )


@agent.on_task_complete("manage_subscription")
def on_manage_subscription_done(call: guava.Call) -> None:
    action = call.get_field("desired_action") or ""
    subscription_id = call.get_variable("subscription_id") or ""

    if "cancel" in action:
        sub = call.get_variable("subscription") or {}
        call.set_task(
            "confirm_cancellation",
            objective="Confirm the customer truly wants to cancel their subscription before proceeding.",
            checklist=[
                guava.Say(
                    "I can help you cancel your subscription. Just to confirm, once cancelled you "
                    "will lose access at the end of your current billing period and will not be charged again."
                ),
                guava.Field(
                    key="cancel_confirm",
                    field_type="multiple_choice",
                    description="Ask if they're sure they want to cancel.",
                    choices=["yes, cancel it", "no, keep it"],
                    required=True,
                ),
            ],
        )
    elif "pause" in action or "update payment" in action:
        call.hangup(
            final_instructions=(
                "Let the caller know that pausing a subscription or updating a payment method "
                "requires logging into their account portal at pinnaclepayments.com, or they can "
                "contact our billing team directly at 1-800-555-0100. "
                "Apologize that you can't complete that action over the phone directly, "
                "and offer any further assistance. Be helpful and friendly."
            )
        )
    elif "billing date" in action:
        sub = call.get_variable("subscription") or {}
        schedule = sub.get("paymentSchedule", {})
        interval = schedule.get("interval", {})
        start_date = schedule.get("startDate", "")
        next_billing = estimate_next_billing_date(
            start_date,
            interval.get("length", 1),
            interval.get("unit", "months"),
        )
        call.hangup(
            final_instructions=(
                f"Let the caller know their next billing date is {next_billing}. "
                "Wish them a great day."
            )
        )
    else:
        # "nothing, just checking"
        call.hangup(
            final_instructions=(
                "Thank the caller for checking in with Pinnacle Payments. "
                "Let them know their subscription is in good standing and wish them a great day. "
                "Keep it warm and brief."
            )
        )


@agent.on_task_complete("confirm_cancellation")
def on_confirm_cancellation_done(call: guava.Call) -> None:
    confirm = call.get_field("cancel_confirm") or ""
    subscription_id = call.get_variable("subscription_id") or ""

    if "yes" in confirm:
        logging.info("Cancelling subscription %s", subscription_id)
        try:
            cancel_subscription(subscription_id)
            logging.info("Subscription %s cancelled successfully", subscription_id)
            call.hangup(
                final_instructions=(
                    "Let the caller know their subscription has been successfully cancelled. "
                    "They will retain access until the end of the current billing period and "
                    "will not be charged again. "
                    "Thank them for being a Pinnacle Payments customer and wish them well."
                )
            )
        except Exception as e:
            logging.error("Failed to cancel subscription %s: %s", subscription_id, e)
            call.hangup(
                final_instructions=(
                    "Apologize and let the caller know there was a technical issue processing "
                    "the cancellation. Let them know their request has been escalated to the "
                    "billing team, who will follow up within one business day to confirm. "
                    "Thank them for their patience."
                )
            )
    else:
        call.hangup(
            final_instructions=(
                "Let the caller know their subscription has been kept active — no changes were made. "
                "Ask if there's anything else you can help them with, then wish them a great day."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])

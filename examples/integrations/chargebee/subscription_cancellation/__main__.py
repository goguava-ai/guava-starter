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


def cancel_subscription(subscription_id: str, end_of_term: bool = True) -> dict | None:
    """Cancels the subscription. end_of_term=True means cancel at period end."""
    resp = requests.post(
        f"{BASE_URL}/subscriptions/{subscription_id}/cancel",
        auth=AUTH,
        data={"end_of_term": "true" if end_of_term else "false"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("subscription")


def format_date(unix_ts: int) -> str:
    return datetime.fromtimestamp(unix_ts, tz=timezone.utc).strftime("%B %d, %Y")


agent = guava.Agent(
    name="Riley",
    organization="Vault",
    purpose=(
        "to help Vault customers cancel their subscription and understand the cancellation process"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "process_cancellation",
        objective=(
            "A customer wants to cancel their Vault subscription. "
            "Verify their identity, understand their reason, and process the cancellation."
        ),
        checklist=[
            guava.Say(
                "Thanks for calling Vault. This is Riley. "
                "I'm sorry to hear you'd like to cancel — let me help you with that."
            ),
            guava.Field(
                key="subscription_id",
                field_type="text",
                description="Ask for their subscription ID from their billing email.",
                required=True,
            ),
            guava.Field(
                key="cancel_reason",
                field_type="multiple_choice",
                description=(
                    "Ask why they're cancelling. Listen empathetically before proceeding."
                ),
                choices=[
                    "too expensive",
                    "not using it enough",
                    "switching to a competitor",
                    "missing features",
                    "technical issues",
                    "other",
                ],
                required=True,
            ),
            guava.Field(
                key="confirmed",
                field_type="multiple_choice",
                description=(
                    "Confirm they'd like to proceed. Let them know their access continues until "
                    "the end of the current billing period."
                ),
                choices=["yes, cancel my subscription", "no, keep my subscription"],
                required=True,
            ),
        ],
    )


@agent.on_task_complete("process_cancellation")
def on_process_cancellation(call: guava.Call) -> None:
    subscription_id = (call.get_field("subscription_id") or "").strip()
    reason = call.get_field("cancel_reason") or ""
    confirmed = call.get_field("confirmed") or ""

    if "keep" in confirmed or "no" in confirmed:
        logging.info("Customer chose to keep subscription %s.", subscription_id)
        call.hangup(
            final_instructions=(
                "Let the caller know we're glad they're staying. "
                "If there's anything we can do to improve their experience, we're always here. "
                "Thank them for calling and wish them a great day."
            )
        )
        return

    logging.info("Cancelling subscription %s — reason: %s", subscription_id, reason)

    try:
        sub = get_subscription(subscription_id)
    except Exception as e:
        logging.error("Subscription lookup failed: %s", e)
        sub = None

    if not sub:
        call.hangup(
            final_instructions=(
                f"Apologize — we couldn't find subscription '{subscription_id}'. "
                "Ask them to check their billing email for the correct ID. "
                "They can also email support to process the cancellation manually."
            )
        )
        return

    current_term_end = sub.get("current_term_end")
    end_date = format_date(current_term_end) if current_term_end else "the end of your current period"

    cancelled_sub = None
    try:
        cancelled_sub = cancel_subscription(subscription_id, end_of_term=True)
        logging.info("Subscription %s cancelled at end of term.", subscription_id)
    except Exception as e:
        logging.error("Cancellation failed: %s", e)

    if cancelled_sub:
        call.hangup(
            final_instructions=(
                f"Let the caller know their Vault subscription has been cancelled. "
                f"They'll continue to have access until {end_date}, after which they won't be charged. "
                "Thank them for being a customer and let them know the door is always open if they return. "
                "Wish them all the best."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                "Apologize — the cancellation couldn't be processed automatically. "
                "Let them know our team will complete the cancellation by end of day and they'll "
                "receive a confirmation email. Thank them for their patience."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])

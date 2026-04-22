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
    resp = requests.get(
        f"{BASE_URL}/v1/customers/search",
        auth=AUTH,
        params={"query": f'email:"{email}"', "limit": 1},
        timeout=10,
    )
    resp.raise_for_status()
    results = resp.json().get("data", [])
    return results[0] if results else None


def list_subscriptions(customer_id: str) -> list:
    resp = requests.get(
        f"{BASE_URL}/v1/subscriptions",
        auth=AUTH,
        params={"customer": customer_id, "status": "active", "limit": 5},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("data", [])


def cancel_at_period_end(sub_id: str, reason: str, feedback: str) -> dict:
    """Marks a subscription to cancel at the end of the current billing period."""
    resp = requests.post(
        f"{BASE_URL}/v1/subscriptions/{sub_id}",
        auth=AUTH,
        data={
            "cancel_at_period_end": "true",
            "cancellation_details[comment]": feedback or reason,
            "cancellation_details[feedback]": _map_feedback(reason),
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def _map_feedback(reason: str) -> str:
    """Maps a spoken reason to a Stripe cancellation_details feedback value."""
    mapping = {
        "too expensive": "too_expensive",
        "missing features": "missing_features",
        "switched to a competitor": "switched_to_competitor",
        "customer service": "customer_service",
        "low quality": "low_quality",
        "unused": "unused",
        "other": "other",
    }
    return mapping.get(reason, "other")


agent = guava.Agent(
    name="Jordan",
    organization="Luminary",
    purpose=(
        "to help Luminary customers who want to cancel their subscription "
        "and understand their reasons for leaving"
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
            "A customer has called to cancel their Luminary subscription. "
            "Verify their identity, look up their subscription, understand why they're leaving, "
            "and set their subscription to cancel at the end of the current billing period."
        ),
        checklist=[
            guava.Say(
                "Thanks for calling Luminary. I'm Jordan. I'm sorry to hear you're looking "
                "to cancel — let me pull up your account and help you with that."
            ),
            guava.Field(
                key="caller_email",
                field_type="text",
                description="Ask for their email address on file.",
                required=True,
            ),
            guava.Field(
                key="cancellation_reason",
                field_type="multiple_choice",
                description=(
                    "Ask why they've decided to cancel. "
                    "Frame it naturally: 'Would you mind sharing the main reason?'"
                ),
                choices=[
                    "too expensive",
                    "missing features",
                    "switched to a competitor",
                    "customer service",
                    "low quality",
                    "unused",
                    "other",
                ],
                required=True,
            ),
            guava.Field(
                key="additional_feedback",
                field_type="text",
                description=(
                    "Ask if there's anything specific that would have changed their mind. "
                    "Capture their response, or skip if they have nothing to add."
                ),
                required=False,
            ),
            guava.Field(
                key="confirmed",
                field_type="multiple_choice",
                description=(
                    "Confirm they'd like to proceed with cancellation. "
                    "Let them know their access continues until the end of the billing period."
                ),
                choices=["yes, cancel", "no, keep my subscription"],
                required=True,
            ),
        ],
    )


@agent.on_task_complete("process_cancellation")
def process_cancellation(call: guava.Call) -> None:
    email = call.get_field("caller_email") or ""
    reason = call.get_field("cancellation_reason") or "other"
    feedback = call.get_field("additional_feedback") or ""
    confirmed = call.get_field("confirmed") or ""

    if "no" in confirmed.lower() or "keep" in confirmed.lower():
        logging.info("Customer chose to keep subscription for email: %s", email)
        call.hangup(
            final_instructions=(
                "Let the caller know their subscription is staying active — no changes were made. "
                "Thank them for staying with Luminary and wish them a great day."
            )
        )
        return

    logging.info("Processing cancellation for email: %s, reason: %s", email, reason)

    try:
        customer = search_customer_by_email(email)
    except Exception as e:
        logging.error("Stripe search failed for %s: %s", email, e)
        customer = None

    if not customer:
        call.hangup(
            final_instructions=(
                "Let the caller know you couldn't locate their account. "
                "Apologize and offer to have a billing specialist follow up by email."
            )
        )
        return

    try:
        subscriptions = list_subscriptions(customer["id"])
    except Exception as e:
        logging.error("Failed to list subscriptions: %s", e)
        subscriptions = []

    if not subscriptions:
        call.hangup(
            final_instructions=(
                "Let the caller know there's no active subscription on their account. "
                "Apologize for any confusion and offer to connect them with billing support."
            )
        )
        return

    sub = subscriptions[0]
    sub_id = sub["id"]
    period_end = sub.get("current_period_end")
    end_date = (
        datetime.fromtimestamp(period_end, tz=timezone.utc).strftime("%B %d, %Y")
        if period_end
        else "the end of your current billing period"
    )

    items = sub.get("items", {}).get("data", [])
    plan_name = "your plan"
    if items:
        price = items[0].get("price", {})
        plan_name = price.get("nickname") or price.get("id") or "your plan"

    try:
        cancel_at_period_end(sub_id, reason, feedback)
        logging.info("Subscription %s set to cancel at period end (%s)", sub_id, end_date)
        call.hangup(
            final_instructions=(
                f"Confirm that '{plan_name}' has been scheduled for cancellation. "
                f"Let the caller know they'll retain full access until {end_date} "
                "and won't be charged after that date. "
                "Thank them sincerely for being a Luminary customer and let them know "
                "we'd love to have them back if anything changes. "
                "Express genuine regret that they're leaving."
            )
        )
    except Exception as e:
        logging.error("Failed to cancel subscription %s: %s", sub_id, e)
        call.hangup(
            final_instructions=(
                "Apologize for a technical issue processing the cancellation. "
                "Let them know their request has been noted and a team member will "
                "process it manually and confirm by email within one business day."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])

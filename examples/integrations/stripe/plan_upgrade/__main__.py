import guava
import os
import logging
from guava import logging_utils
import requests


STRIPE_SECRET_KEY = os.environ["STRIPE_SECRET_KEY"]
AUTH = (STRIPE_SECRET_KEY, "")
BASE_URL = "https://api.stripe.com"

# Map plan names to Stripe Price IDs — configure these for your product.
PLAN_PRICE_IDS: dict[str, str] = {
    "starter": os.environ.get("STRIPE_PRICE_STARTER", ""),
    "professional": os.environ.get("STRIPE_PRICE_PROFESSIONAL", ""),
    "enterprise": os.environ.get("STRIPE_PRICE_ENTERPRISE", ""),
}
AVAILABLE_PLANS = [k for k, v in PLAN_PRICE_IDS.items() if v]


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


def upgrade_subscription(sub_id: str, sub_item_id: str, new_price_id: str) -> dict:
    """Swaps the subscription item to a new price with immediate proration."""
    resp = requests.post(
        f"{BASE_URL}/v1/subscriptions/{sub_id}",
        auth=AUTH,
        data={
            "items[0][id]": sub_item_id,
            "items[0][price]": new_price_id,
            "proration_behavior": "create_prorations",
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


agent = guava.Agent(
    name="Alex",
    organization="Luminary",
    purpose=(
        "to help Luminary customers upgrade their subscription plan"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "process_upgrade",
        objective=(
            "A customer has called to upgrade their Luminary subscription. "
            "Verify their identity, look up their current plan, confirm which plan "
            "they'd like to move to, and process the upgrade immediately with proration."
        ),
        checklist=[
            guava.Say(
                "Thanks for calling Luminary. I'm Alex. "
                "I'd be happy to help you upgrade your plan. Let me pull up your account."
            ),
            guava.Field(
                key="caller_email",
                field_type="text",
                description="Ask for their email address on file.",
                required=True,
            ),
            guava.Field(
                key="desired_plan",
                field_type="multiple_choice",
                description=(
                    "Ask which plan they'd like to upgrade to. "
                    "Briefly describe the options if they're unsure."
                ),
                choices=AVAILABLE_PLANS or ["starter", "professional", "enterprise"],
                required=True,
            ),
            guava.Field(
                key="confirmed",
                field_type="multiple_choice",
                description=(
                    "Confirm they'd like to proceed with the upgrade. "
                    "Let them know a prorated charge will be applied immediately "
                    "for the remainder of the current billing period."
                ),
                choices=["yes, upgrade now", "no, cancel"],
                required=True,
            ),
        ],
    )


@agent.on_task_complete("process_upgrade")
def process_upgrade(call: guava.Call) -> None:
    email = call.get_field("caller_email") or ""
    desired_plan = call.get_field("desired_plan") or ""
    confirmed = call.get_field("confirmed") or ""

    if "no" in confirmed.lower() or "cancel" in confirmed.lower():
        call.hangup(
            final_instructions=(
                "Let the caller know no changes were made to their account. "
                "Thank them for calling and let them know we're here whenever they're ready."
            )
        )
        return

    new_price_id = PLAN_PRICE_IDS.get(desired_plan, "")
    if not new_price_id:
        logging.error("No price ID configured for plan: %s", desired_plan)
        call.hangup(
            final_instructions=(
                f"Apologize and let the caller know the '{desired_plan}' plan isn't "
                "available to configure right now. Offer to have a billing specialist "
                "contact them by email to complete the upgrade."
            )
        )
        return

    logging.info("Processing plan upgrade to %s for email: %s", desired_plan, email)

    try:
        customer = search_customer_by_email(email)
    except Exception as e:
        logging.error("Stripe search failed for %s: %s", email, e)
        customer = None

    if not customer:
        call.hangup(
            final_instructions=(
                "Let the caller know you couldn't locate their account. "
                "Apologize and offer to transfer them to a billing specialist."
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
                "Let the caller know there's no active subscription on their account to upgrade. "
                "Offer to transfer them to a billing specialist."
            )
        )
        return

    sub = subscriptions[0]
    sub_id = sub["id"]
    items = sub.get("items", {}).get("data", [])

    if not items:
        call.hangup(
            final_instructions=(
                "Apologize for a technical issue and offer to have a specialist follow up by email."
            )
        )
        return

    current_item = items[0]
    sub_item_id = current_item["id"]
    current_plan = current_item.get("price", {}).get("nickname") or "your current plan"

    # Don't upgrade to the same plan
    current_price_id = current_item.get("price", {}).get("id", "")
    if current_price_id == new_price_id:
        call.hangup(
            final_instructions=(
                f"Let the caller know they're already on the {desired_plan} plan."
            )
        )
        return

    name = customer.get("name") or "there"
    logging.info(
        "Upgrading subscription %s from %s (item %s) to price %s",
        sub_id, current_plan, sub_item_id, new_price_id,
    )

    try:
        upgrade_subscription(sub_id, sub_item_id, new_price_id)
        logging.info("Subscription %s upgraded to %s", sub_id, desired_plan)
        call.hangup(
            final_instructions=(
                f"Congratulate {name} on their upgrade to the {desired_plan} plan. "
                "Let them know the change is effective immediately and a prorated invoice "
                "will appear on their account for the remainder of the billing period. "
                "Ask if there's anything else they'd like to know about the new plan. "
                "Be warm and enthusiastic."
            )
        )
    except Exception as e:
        logging.error("Failed to upgrade subscription %s: %s", sub_id, e)
        call.hangup(
            final_instructions=(
                f"Apologize to {name} for a technical issue. Let them know their upgrade request "
                "has been noted and a billing specialist will process it and confirm by email "
                "within one business day."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])

import logging
import os

import guava
import requests
from guava import logging_utils

AFTERSHIP_API_KEY = os.environ["AFTERSHIP_API_KEY"]
HEADERS = {
    "as-api-key": AFTERSHIP_API_KEY,
    "Content-Type": "application/json",
}
BASE_URL = "https://api.aftership.com/v4"

# Slug for the return carrier configured in AfterShip.
RETURN_CARRIER_SLUG = os.environ.get("AFTERSHIP_RETURN_CARRIER_SLUG", "ups")


def create_return_tracking(
    tracking_number: str,
    title: str,
    customer_name: str,
    customer_email: str,
    order_id: str,
) -> dict:
    """Creates a return tracking record in AfterShip."""
    payload = {
        "tracking": {
            "tracking_number": tracking_number,
            "slug": RETURN_CARRIER_SLUG,
            "title": title,
            "customer_name": customer_name,
            "emails": [customer_email] if customer_email else [],
            "order_id": order_id,
            "tag": "Pending",
        }
    }
    resp = requests.post(
        f"{BASE_URL}/trackings",
        headers=HEADERS,
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("data", {}).get("tracking", {})


agent = guava.Agent(
    name="Jordan",
    organization="Meridian Commerce",
    purpose=(
        "to help Meridian Commerce customers initiate returns and get their return "
        "shipment set up"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "register_return",
        objective=(
            "A customer is calling to return an order. Collect their information and the "
            "return tracking number from the pre-paid label we provide, then register the "
            "return in our system so they can be notified when we receive it."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling Meridian Commerce returns. This is Jordan. "
                "I'll help you get your return set up today."
            ),
            guava.Field(
                key="customer_name",
                field_type="text",
                description="Ask for the customer's full name.",
                required=True,
            ),
            guava.Field(
                key="customer_email",
                field_type="text",
                description=(
                    "Ask for their email address so we can send return updates."
                ),
                required=True,
            ),
            guava.Field(
                key="order_id",
                field_type="text",
                description=(
                    "Ask for their order number. It starts with '#' and is on their "
                    "original order confirmation."
                ),
                required=True,
            ),
            guava.Field(
                key="return_tracking_number",
                field_type="text",
                description=(
                    "Ask for the tracking number printed on the return label they received. "
                    "If they don't have a pre-paid label yet, note that and skip this field."
                ),
                required=False,
            ),
            guava.Field(
                key="return_reason",
                field_type="multiple_choice",
                description="Ask why they're returning the item.",
                choices=[
                    "wrong item received",
                    "item arrived damaged",
                    "item did not match description",
                    "changed my mind",
                    "other",
                ],
                required=True,
            ),
        ],
    )


@agent.on_task_complete("register_return")
def on_done(call: guava.Call) -> None:
    name = call.get_field("customer_name") or "Customer"
    email = call.get_field("customer_email") or ""
    order_id = call.get_field("order_id") or "unknown"
    return_tracking = (call.get_field("return_tracking_number") or "").strip()
    reason = call.get_field("return_reason") or "other"

    logging.info(
        "Processing return for %s, order %s, reason: %s", name, order_id, reason
    )

    if not return_tracking:
        call.hangup(
            final_instructions=(
                f"Let {name} know that since they don't have a return label yet, our team "
                "will email them a pre-paid return label within one business day. "
                "Once they receive it, they can drop the package off at any carrier location. "
                "Thank them for their patience."
            )
        )
        return

    try:
        tracking = create_return_tracking(
            tracking_number=return_tracking,
            title=f"Return for order {order_id}",
            customer_name=name,
            customer_email=email,
            order_id=order_id,
        )
        tracking_id = tracking.get("id") or return_tracking
        logging.info("Return tracking created: %s", tracking_id)

        call.hangup(
            final_instructions=(
                f"Let {name} know their return has been registered in our system. "
                f"Their return tracking number is {return_tracking}. "
                "Let them know they'll receive email updates as we process the return, "
                "and that their refund will be issued within 3–5 business days of receiving the item. "
                "Thank them for shopping with Meridian Commerce."
            )
        )
    except Exception as e:
        logging.error("Failed to create return tracking for order %s: %s", order_id, e)
        call.hangup(
            final_instructions=(
                f"Apologize to {name} for a technical issue and let them know our returns "
                "team will follow up by email within one business day to confirm their return. "
                "Their information has been noted. Thank them for their patience."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])

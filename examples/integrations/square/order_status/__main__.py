import logging
import os

import guava
import requests
from guava import logging_utils

BASE_URL = os.environ.get("SQUARE_BASE_URL", "https://connect.squareupsandbox.com")
SQUARE_VERSION = "2024-01-18"


def get_headers() -> dict:
    return {
        "Authorization": f"Bearer {os.environ['SQUARE_ACCESS_TOKEN']}",
        "Square-Version": SQUARE_VERSION,
        "Content-Type": "application/json",
    }


def get_order(order_id: str) -> dict | None:
    resp = requests.get(
        f"{BASE_URL}/v2/orders/{order_id}",
        headers=get_headers(),
        timeout=10,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json().get("order")


def format_amount(amount_money: dict) -> str:
    amount = amount_money.get("amount", 0)
    currency = amount_money.get("currency", "USD")
    return f"${amount / 100:,.2f} {currency}"


agent = guava.Agent(
    name="Drew",
    organization="Harbor Market",
    purpose="to help Harbor Market customers check the status of their orders",
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "lookup_order",
        objective="A customer has called to check on an order. Collect their order ID and look it up.",
        checklist=[
            guava.Say(
                "Thanks for calling Harbor Market. This is Drew. "
                "I can help you check on an order today."
            ),
            guava.Field(
                key="email",
                field_type="text",
                description="Ask for the email address used for their order.",
                required=True,
            ),
            guava.Field(
                key="order_id",
                field_type="text",
                description=(
                    "Ask for their order ID. "
                    "They can find it in their order confirmation email from Harbor Market."
                ),
                required=True,
            ),
        ],
    )


@agent.on_task_complete("lookup_order")
def lookup_order(call: guava.Call) -> None:
    order_id = (call.get_field("order_id") or "").strip()
    email = call.get_field("email") or ""

    logging.info("Looking up Square order %s for %s", order_id, email)

    try:
        order = get_order(order_id)
    except Exception as e:
        logging.error("Order lookup failed: %s", e)
        order = None

    if not order:
        call.hangup(
            final_instructions=(
                f"Let the caller know we couldn't find an order with ID '{order_id}'. "
                "Ask them to check their confirmation email for the correct order ID. "
                "Be apologetic and helpful."
            )
        )
        return

    state = order.get("state", "UNKNOWN")
    total_money = order.get("total_money", {})
    total_str = format_amount(total_money) if total_money else ""
    fulfillments = order.get("fulfillments", [])
    fulfillment_state = ""
    tracking = ""
    if fulfillments:
        f = fulfillments[0]
        fulfillment_state = f.get("state", "")
        shipment = f.get("shipment_details", {})
        tracking = shipment.get("tracking_number", "")
        carrier = shipment.get("carrier", "")
        if tracking and carrier:
            tracking = f"{carrier} tracking: {tracking}"

    state_map = {
        "OPEN": "open and being processed",
        "COMPLETED": "completed",
        "CANCELED": "cancelled",
        "DRAFT": "in draft",
    }
    state_display = state_map.get(state, state.lower())

    fulfillment_map = {
        "PROPOSED": "pending",
        "RESERVED": "reserved",
        "PREPARED": "prepared and ready",
        "COMPLETED": "fulfilled and shipped",
        "CANCELED": "cancelled",
        "FAILED": "failed",
    }
    fulfillment_display = fulfillment_map.get(fulfillment_state, fulfillment_state.lower()) if fulfillment_state else ""

    logging.info("Order %s: state=%s, fulfillment=%s", order_id, state, fulfillment_state)

    call.hangup(
        final_instructions=(
            f"Let the caller know their order {order_id} is currently {state_display}. "
            + (f"The order total is {total_str}. " if total_str else "")
            + (f"The fulfillment status is {fulfillment_display}. " if fulfillment_display else "")
            + (f"{tracking}. " if tracking else "")
            + "If they have concerns about a cancelled or delayed order, let them know our team can help. "
            "Be friendly and thorough."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])

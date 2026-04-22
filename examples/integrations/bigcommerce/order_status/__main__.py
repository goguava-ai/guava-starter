import json
import logging
import os
from datetime import datetime, timezone

import guava
import requests
from guava import logging_utils

STORE_HASH = os.environ["BIGCOMMERCE_STORE_HASH"]
AUTH_TOKEN = os.environ["BIGCOMMERCE_AUTH_TOKEN"]
V2_BASE = f"https://api.bigcommerce.com/stores/{STORE_HASH}/v2"

HEADERS = {
    "X-Auth-Token": AUTH_TOKEN,
    "Content-Type": "application/json",
    "Accept": "application/json",
}

STATUS_MAP = {
    0: "Incomplete",
    1: "Pending",
    2: "Shipped",
    3: "Partially Shipped",
    4: "Refunded",
    5: "Cancelled",
    7: "Awaiting Payment",
    8: "Awaiting Pickup",
    9: "Awaiting Shipment",
    10: "Completed",
    11: "Awaiting Fulfillment",
    12: "Manual Verification Required",
}


agent = guava.Agent(
    name="Jordan",
    organization="Harbor House",
    purpose="to help Harbor House customers check on their orders and get updates about their shopping experience",
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "collect_order_info",
        objective=(
            "A customer has called Harbor House to check on the status of their order. "
            "Greet them warmly, collect their email address, and ask if they have their "
            "order number handy. Then look up their order and read back the details."
        ),
        checklist=[
            guava.Say(
                "Thanks for calling Harbor House! I'm Jordan, and I'm happy to help you "
                "check on your order today."
            ),
            guava.Field(
                key="email",
                description="Ask for their email address so we can pull up their account.",
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="order_number",
                description=(
                    "Ask if they have their order number handy — if not, that's okay. "
                    "We can find their most recent order with just their email. "
                    "Capture the order number as a plain number, or leave blank if they don't have it."
                ),
                field_type="text",
                required=False,
            ),
        ],
    )


@agent.on_task_complete("collect_order_info")
def on_collect_done(call: guava.Call) -> None:
    email = call.get_field("email")
    order_number = call.get_field("order_number")

    try:
        resp = requests.get(
            f"{V2_BASE}/orders",
            headers=HEADERS,
            params={"email": email, "sort": "date_created:desc", "limit": 5},
            timeout=10,
        )
        resp.raise_for_status()
        orders = resp.json()
    except Exception as e:
        logging.error("Failed to fetch orders for %s: %s", email, e)
        call.hangup(
            final_instructions=(
                "Apologize to the customer and let them know we were unable to retrieve "
                "their order information at this time. Ask them to visit harborhouse.com "
                "or try again shortly. Thank them for calling Harbor House."
            )
        )
        return

    if not orders:
        call.hangup(
            final_instructions=(
                "Let the customer know that no orders were found for the email address "
                "they provided. Suggest they check if they used a different email, or "
                "visit harborhouse.com and sign in to view their order history. "
                "Thank them for calling Harbor House."
            )
        )
        return

    # Match by order number if provided, otherwise use the most recent
    order = None
    if order_number:
        for o in orders:
            if str(o.get("id")) == str(order_number).strip():
                order = o
                break
        if order is None:
            call.hangup(
                final_instructions=(
                    f"Let the customer know that order #{order_number} could not be found "
                    "under the email address they provided. Ask them to double-check the "
                    "order number and email, or visit harborhouse.com to view their orders. "
                    "Thank them for calling Harbor House."
                )
            )
            return
    else:
        order = orders[0]

    order_id = order.get("id")
    status_id = order.get("status_id", -1)
    status_label = STATUS_MAP.get(status_id, order.get("status", "Unknown"))
    total = order.get("total_inc_tax", "")
    date_created = order.get("date_created", "")
    billing = order.get("billing_address", {})
    first_name = billing.get("first_name", "")

    # Format date for readability
    try:
        dt = datetime.strptime(date_created, "%a, %d %b %Y %H:%M:%S %z")
        display_date = dt.strftime("%B %-d, %Y")
    except (ValueError, AttributeError):
        display_date = date_created

    # Fetch line items
    items_summary = ""
    try:
        items_resp = requests.get(
            f"{V2_BASE}/orders/{order_id}/products",
            headers=HEADERS,
            timeout=10,
        )
        items_resp.raise_for_status()
        items = items_resp.json()
        if items:
            item_parts = []
            for item in items:
                name = item.get("name", "item")
                qty = item.get("quantity", 1)
                item_parts.append(f"{qty}x {name}")
            items_summary = ", ".join(item_parts)
    except Exception as e:
        logging.warning("Could not fetch line items for order %s: %s", order_id, e)

    print(json.dumps({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "order_id": order_id,
        "status_id": status_id,
        "status_label": status_label,
        "total": total,
        "date_created": date_created,
        "items_summary": items_summary,
    }, indent=2))

    call.set_variable("order", order)

    items_line = f" Your order includes: {items_summary}." if items_summary else ""
    greeting = f"{first_name}, " if first_name else ""

    call.set_task(
        "order_status_followup",
        objective=(
            f"You have pulled up order #{order_id} for the customer. "
            f"Read back the order details and ask if they need anything else."
        ),
        checklist=[
            guava.Say(
                f"I found your order, {greeting}here are the details. "
                f"Order number {order_id}, placed on {display_date}. "
                f"The current status is: {status_label}.{items_line} "
                f"The order total was ${total}."
            ),
            guava.Field(
                key="next_action",
                description=(
                    "Ask if there is anything else you can help them with. "
                    "Offer these options and capture their choice: "
                    "'track my shipment', 'cancel my order', 'speak to someone', or 'no, all good'."
                ),
                field_type="multiple_choice",
                choices=["track my shipment", "cancel my order", "speak to someone", "no, all good"],
                required=True,
            ),
        ],
    )


@agent.on_task_complete("order_status_followup")
def on_followup_done(call: guava.Call) -> None:
    action = call.get_field("next_action")
    order_number = call.get_field("order_number")
    label = (action or "").strip().lower()

    if label == "track my shipment":
        call.hangup(
            final_instructions=(
                "Let the customer know they can track their shipment by visiting "
                "harborhouse.com/orders and signing into their account — a tracking link "
                "is available once the order has shipped. If it hasn't shipped yet, "
                "assure them they'll receive an email with tracking details as soon as it does. "
                "Thank them for calling Harbor House and wish them a great day."
            )
        )
    elif label == "cancel my order":
        call.hangup(
            final_instructions=(
                "Let the customer know you'll note their cancellation request. "
                "Advise them to call back and use the cancellation option for the fastest service, "
                "or to visit harborhouse.com and use the Help Center to submit a cancellation request. "
                "Thank them for calling Harbor House."
            )
        )
    elif label == "speak to someone":
        call.hangup(
            final_instructions=(
                "Let the customer know you are transferring them to the Harbor House support team. "
                "Thank them for their patience and wish them a great rest of their day."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                "Thank the customer for calling Harbor House and let them know their order "
                "details have been noted. Wish them a great day."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])

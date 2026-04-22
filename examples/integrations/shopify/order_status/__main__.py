import logging
import os

import guava
import requests
from guava import logging_utils

STORE = os.environ["SHOPIFY_STORE"]
BASE_URL = f"https://{STORE}.myshopify.com/admin/api/2026-01"


def get_headers() -> dict:
    return {
        "X-Shopify-Access-Token": os.environ["SHOPIFY_ACCESS_TOKEN"],
        "Content-Type": "application/json",
    }


def search_orders_by_email(email: str) -> list:
    resp = requests.get(
        f"{BASE_URL}/orders.json",
        headers=get_headers(),
        params={"email": email, "status": "any", "limit": 5},
        timeout=10,
    )
    if not resp.ok:
        return []
    return resp.json().get("orders", [])


def get_order(order_id: str) -> dict | None:
    resp = requests.get(
        f"{BASE_URL}/orders/{order_id}.json",
        headers=get_headers(),
        timeout=10,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json().get("order")


agent = guava.Agent(
    name="Casey",
    organization="Kestrel Goods",
    purpose="to help Kestrel Goods customers check the status of their orders",
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "lookup_order",
        objective=(
            "A customer has called to check on an order. "
            "Verify their email and look up their recent orders."
        ),
        checklist=[
            guava.Say(
                "Thanks for calling Kestrel Goods. This is Casey. "
                "I can help you check on an order today."
            ),
            guava.Field(
                key="email",
                field_type="text",
                description="Ask for the email address used when placing the order.",
                required=True,
            ),
            guava.Field(
                key="order_name",
                field_type="text",
                description=(
                    "Ask if they have their order number handy "
                    "(e.g., #1042). It's optional — we can look up by email too."
                ),
                required=False,
            ),
        ],
    )


@agent.on_task_complete("lookup_order")
def on_done(call: guava.Call) -> None:
    email = (call.get_field("email") or "").strip().lower()
    order_name = (call.get_field("order_name") or "").strip()

    logging.info("Looking up Shopify orders for %s (order: %s)", email, order_name)

    try:
        orders = search_orders_by_email(email)
    except Exception as e:
        logging.error("Shopify order lookup failed: %s", e)
        orders = []

    if not orders:
        call.hangup(
            final_instructions=(
                f"Let the caller know we couldn't find any orders linked to '{email}'. "
                "Ask them to double-check the email they used when ordering. "
                "They can also check their order status at kestrelgoods.com. Be apologetic."
            )
        )
        return

    # Filter by order name if provided
    if order_name:
        clean_name = order_name.lstrip("#")
        matching = [o for o in orders if str(o.get("order_number", "")) == clean_name or o.get("name", "").lstrip("#") == clean_name]
        if matching:
            orders = matching

    order = orders[0]
    order_number = order.get("name", "")
    financial_status = order.get("financial_status", "")
    fulfillment_status = order.get("fulfillment_status") or "unfulfilled"
    total_price = order.get("total_price", "")
    created_at = order.get("created_at", "")[:10]

    # Get tracking info from fulfillments
    tracking_info = []
    for fulfillment in order.get("fulfillments", []):
        tracking_number = fulfillment.get("tracking_number", "")
        tracking_company = fulfillment.get("tracking_company", "")
        if tracking_number:
            tracking_info.append(f"{tracking_company}: {tracking_number}")

    status_map = {
        "unfulfilled": "being processed and not yet shipped",
        "partial": "partially shipped",
        "fulfilled": "shipped",
        "restocked": "returned to stock",
    }
    fulfillment_display = status_map.get(fulfillment_status, fulfillment_status)

    financial_map = {
        "paid": "paid",
        "pending": "pending payment",
        "refunded": "refunded",
        "partially_refunded": "partially refunded",
        "voided": "voided",
    }
    financial_display = financial_map.get(financial_status, financial_status)

    logging.info("Order %s: financial=%s, fulfillment=%s", order_number, financial_status, fulfillment_status)

    call.hangup(
        final_instructions=(
            f"Let the caller know their order {order_number}"
            + (f" placed on {created_at}" if created_at else "")
            + (f" for ${total_price}" if total_price else "")
            + f" is currently {fulfillment_display} and payment is {financial_display}. "
            + (f"Tracking: {'; '.join(tracking_info)}. " if tracking_info else "")
            + "If they have questions about their order or want to make changes, let them know we're here to help. "
            "Wish them a great day."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])

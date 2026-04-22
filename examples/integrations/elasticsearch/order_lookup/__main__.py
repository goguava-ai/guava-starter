import guava
import os
import logging
from guava import logging_utils
import requests


ES_URL = os.environ["ELASTICSEARCH_URL"].rstrip("/")
ORDER_INDEX = os.environ.get("ELASTICSEARCH_ORDER_INDEX", "orders")


def get_headers() -> dict:
    return {
        "Authorization": f"ApiKey {os.environ['ELASTICSEARCH_API_KEY']}",
        "Content-Type": "application/json",
    }


def find_orders_by_email(email: str) -> list[dict]:
    body = {
        "query": {"term": {"customer_email.keyword": email}},
        "sort": [{"created_at": {"order": "desc"}}],
        "size": 5,
        "_source": [
            "order_number", "status", "total", "currency",
            "created_at", "items", "shipping_status", "tracking_number",
        ],
    }
    resp = requests.post(
        f"{ES_URL}/{ORDER_INDEX}/_search",
        headers=get_headers(),
        json=body,
        timeout=10,
    )
    resp.raise_for_status()
    hits = resp.json().get("hits", {}).get("hits", [])
    return [h["_source"] for h in hits]


def find_order_by_number(order_number: str) -> dict | None:
    body = {
        "query": {"term": {"order_number.keyword": order_number.lstrip("#")}},
        "size": 1,
        "_source": [
            "order_number", "status", "total", "currency",
            "created_at", "items", "shipping_status", "tracking_number",
        ],
    }
    resp = requests.post(
        f"{ES_URL}/{ORDER_INDEX}/_search",
        headers=get_headers(),
        json=body,
        timeout=10,
    )
    resp.raise_for_status()
    hits = resp.json().get("hits", {}).get("hits", [])
    return hits[0]["_source"] if hits else None


agent = guava.Agent(
    name="Morgan",
    organization="Apex Store",
    purpose="to help Apex Store customers look up their orders by phone",
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "order_lookup",
        objective=(
            "A customer has called to look up an order. "
            "Verify their email, find their most recent orders, and read back the status and details."
        ),
        checklist=[
            guava.Say(
                "Welcome to Apex Store. This is Morgan. I can help you look up your order."
            ),
            guava.Field(
                key="email",
                field_type="text",
                description="Ask for the email address on the order.",
                required=True,
            ),
            guava.Field(
                key="order_number",
                field_type="text",
                description="Ask for the order number if they have it (optional).",
                required=False,
            ),
        ],
    )


@agent.on_task_complete("order_lookup")
def on_done(call: guava.Call) -> None:
    email = call.get_field("email") or ""
    order_number = call.get_field("order_number") or ""

    logging.info("Looking up order: email=%s, order_number=%s", email, order_number)

    order = None
    try:
        if order_number:
            order = find_order_by_number(order_number)
        if not order and email:
            orders = find_orders_by_email(email)
            order = orders[0] if orders else None
        logging.info("Found order: %s", order.get("order_number") if order else None)
    except Exception as e:
        logging.error("Failed to look up order: %s", e)

    if not order:
        call.hangup(
            final_instructions=(
                "Let the customer know we couldn't find an order matching that information. "
                "Ask them to double-check their email and call back. "
                "Thank them for calling Apex Store."
            )
        )
        return

    order_num = order.get("order_number", "")
    status = order.get("status", "unknown")
    total = order.get("total", 0)
    currency = order.get("currency", "USD")
    shipping_status = order.get("shipping_status", "")
    tracking = order.get("tracking_number", "")
    items = order.get("items", [])
    item_count = len(items) if isinstance(items, list) else 0

    details = f"Order #{order_num}: {item_count} item(s), total ${total:.2f} {currency}, status: {status}."
    if shipping_status:
        details += f" Shipping: {shipping_status}."
    if tracking:
        details += f" Tracking number: {tracking}."

    call.hangup(
        final_instructions=(
            f"Read the following order details to the customer: {details} "
            "Thank them for shopping with Apex Store."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])

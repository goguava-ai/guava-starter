import guava
import os
import logging
from guava import logging_utils
import requests


STORE = os.environ["SHOPIFY_STORE"]
BASE_URL = f"https://{STORE}.myshopify.com/admin/api/2026-01"


def get_headers() -> dict:
    return {
        "X-Shopify-Access-Token": os.environ["SHOPIFY_ACCESS_TOKEN"],
        "Content-Type": "application/json",
    }


def find_order(email: str, order_number: str = "") -> dict | None:
    params: dict = {"email": email, "status": "any", "limit": 10}
    resp = requests.get(f"{BASE_URL}/orders.json", headers=get_headers(), params=params, timeout=10)
    resp.raise_for_status()
    orders = resp.json().get("orders", [])
    if order_number:
        num = order_number.lstrip("#")
        orders = [o for o in orders if str(o.get("order_number", "")) == num]
    fulfilled = [o for o in orders if o.get("fulfillment_status") == "fulfilled"]
    return fulfilled[0] if fulfilled else (orders[0] if orders else None)


def get_line_items(order: dict) -> list[dict]:
    return order.get("line_items", [])


def create_return(order_id: int, line_item_id: int, quantity: int, reason: str) -> dict | None:
    payload = {
        "return": {
            "order_id": order_id,
            "line_items": [
                {
                    "line_item_id": line_item_id,
                    "quantity": quantity,
                    "return_reason": reason,
                }
            ],
            "notify_customer": True,
        }
    }
    resp = requests.post(
        f"{BASE_URL}/returns.json",
        headers=get_headers(),
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("return")


agent = guava.Agent(
    name="Casey",
    organization="Kestrel Goods",
    purpose="to help Kestrel Goods customers initiate product returns",
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "create_return",
        objective=(
            "A customer has called to initiate a return for an order. "
            "Collect their order details, reason for return, and create the return."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling Kestrel Goods. This is Casey. "
                "I'd be happy to help you start a return today."
            ),
            guava.Field(
                key="email",
                field_type="text",
                description="Ask for the email address used to place the order.",
                required=True,
            ),
            guava.Field(
                key="order_number",
                field_type="text",
                description="Ask for the order number (it starts with #).",
                required=True,
            ),
            guava.Field(
                key="return_reason",
                field_type="multiple_choice",
                description="Ask why they are returning the item.",
                choices=["defective", "wrong item", "not as described", "changed mind", "other"],
                required=True,
            ),
            guava.Field(
                key="item_description",
                field_type="text",
                description="Ask which item they'd like to return (product name or brief description).",
                required=True,
            ),
        ],
    )


@agent.on_task_complete("create_return")
def on_done(call: guava.Call) -> None:
    email = call.get_field("email") or ""
    order_number = call.get_field("order_number") or ""
    return_reason = call.get_field("return_reason") or "other"
    item_description = call.get_field("item_description") or ""

    reason_map = {
        "defective": "DEFECTIVE",
        "wrong item": "WRONG_ITEM",
        "not as described": "NOT_AS_DESCRIBED",
        "changed mind": "CUSTOMER_CHANGED_MIND",
        "other": "OTHER",
    }
    reason_code = reason_map.get(return_reason, "OTHER")

    order = None
    try:
        order = find_order(email, order_number)
    except Exception as e:
        logging.error("Failed to find order: %s", e)

    if not order:
        call.hangup(
            final_instructions=(
                "Let the customer know we couldn't locate a fulfilled order with that email and order number. "
                "Ask them to double-check and call back, or email support@kestrelgoods.com. "
                "Thank them for their patience."
            )
        )
        return

    order_id = order["id"]
    order_num = order.get("order_number", "")
    line_items = get_line_items(order)

    # Try to match the described item to a line item
    matched_item = None
    if line_items:
        desc_lower = item_description.lower()
        for item in line_items:
            title = item.get("title", "").lower()
            variant = item.get("variant_title", "").lower()
            if desc_lower in title or desc_lower in variant or title in desc_lower:
                matched_item = item
                break
        if not matched_item:
            matched_item = line_items[0]

    created = None
    if matched_item:
        try:
            created = create_return(
                order_id=order_id,
                line_item_id=matched_item["id"],
                quantity=1,
                reason=reason_code,
            )
            logging.info("Created return for order %s, item %s", order_num, matched_item.get("title"))
        except Exception as e:
            logging.error("Failed to create return: %s", e)

    if created:
        call.hangup(
            final_instructions=(
                f"Let the customer know the return for order #{order_num} has been initiated. "
                "They'll receive a confirmation email with return instructions shortly. "
                "Once the item is received, their refund will be processed within 5-7 business days. "
                "Thank them for shopping with Kestrel Goods."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Apologize — we were unable to create the return for order #{order_num} automatically. "
                "Ask them to email support@kestrelgoods.com with their order number and reason for return, "
                "and the team will handle it within one business day. Thank them for their patience."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])

import guava
import os
import logging
from guava import logging_utils
import requests


STORE_HASH = os.environ["BIGCOMMERCE_STORE_HASH"]
ACCESS_TOKEN = os.environ["BIGCOMMERCE_ACCESS_TOKEN"]
BASE_V2 = f"https://api.bigcommerce.com/stores/{STORE_HASH}/v2"

HEADERS = {
    "X-Auth-Token": ACCESS_TOKEN,
    "Content-Type": "application/json",
    "Accept": "application/json",
}

# Order status IDs that are eligible for a refund
REFUNDABLE_STATUS_IDS = {2, 3, 9, 10, 11}  # Shipped, Partially Shipped, Awaiting Shipment, Completed, Awaiting Fulfillment

ORDER_STATUSES = {
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


def fetch_order(order_id: int):
    resp = requests.get(
        f"{BASE_V2}/orders/{order_id}",
        headers=HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_order_products(order_id: int):
    resp = requests.get(
        f"{BASE_V2}/orders/{order_id}/products",
        headers=HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def post_refund(order_id: int, items: list, reason: str):
    """
    POST /v2/orders/{id}/refunds
    items: list of dicts with keys item_type ("PRODUCT"|"SHIPPING"|"HANDLING"),
           item_id (product line item id), and quantity.
    """
    payload = {
        "items": items,
        "reason": reason,
        "notify_customer": True,
    }
    resp = requests.post(
        f"{BASE_V2}/orders/{order_id}/refunds",
        headers=HEADERS,
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


agent = guava.Agent(
    name="Sierra",
    organization="Crestline Outdoor Gear",
    purpose="to help customers request a refund for their order",
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "refund_request",
        objective=(
            "Collect the customer's order number and reason for the refund, "
            "verify the order exists and is eligible, then process the refund."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling Crestline Outdoor Gear. This is Sierra. "
                "I'm sorry to hear you'd like a refund — I'll do my best to help you quickly."
            ),
            guava.Field(
                key="order_id",
                field_type="integer",
                description="Ask the caller for their order number.",
                required=True,
            ),
            guava.Field(
                key="reason",
                field_type="multiple_choice",
                description="Ask the caller why they are requesting a refund.",
                choices=[
                    "item arrived damaged",
                    "wrong item received",
                    "item not as described",
                    "changed my mind",
                    "order arrived too late",
                    "other",
                ],
                required=True,
            ),
        ],
    )


@agent.on_task_complete("refund_request")
def on_done(call: guava.Call) -> None:
    raw_order_id = call.get_field("order_id")
    reason = call.get_field("reason")

    try:
        order_id = int(str(raw_order_id).strip())
    except (ValueError, TypeError):
        call.hangup(
            final_instructions=(
                "Tell the caller the order number they provided doesn't look valid. "
                "Ask them to call back with their order confirmation email handy. "
                "Be apologetic and helpful."
            )
        )
        return

    try:
        order = fetch_order(order_id)
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            call.hangup(
                final_instructions=(
                    f"Tell the caller that order #{order_id} could not be found. "
                    "Suggest they check their confirmation email for the correct number "
                    "or contact support. Be apologetic."
                )
            )
        else:
            logging.error("Error fetching order %s: %s", order_id, e)
            call.hangup(
                final_instructions=(
                    "Apologize and tell the caller there was a system error processing "
                    "their request. Ask them to try again or contact support."
                )
            )
        return
    except Exception as e:
        logging.error("Unexpected error fetching order %s: %s", order_id, e)
        call.hangup(
            final_instructions=(
                "Apologize and tell the caller there was an unexpected error. "
                "Direct them to contact customer support."
            )
        )
        return

    status_id = order.get("status_id")
    status_label = ORDER_STATUSES.get(status_id, f"status {status_id}")

    if status_id not in REFUNDABLE_STATUS_IDS:
        call.hangup(
            final_instructions=(
                f"Tell the caller that order #{order_id} currently has a status of "
                f"'{status_label}', which means it cannot be automatically refunded at this time. "
                "If the order is already refunded or cancelled, let them know. "
                "Otherwise, direct them to contact support for assistance. Be empathetic."
            )
        )
        return

    # Fetch line items to build the refund payload
    refund_result = None
    try:
        products = fetch_order_products(order_id)
        items = [
            {
                "item_type": "PRODUCT",
                "item_id": p["id"],
                "quantity": p["quantity"],
            }
            for p in products
            if isinstance(p, dict) and p.get("quantity", 0) > 0
        ]
        if items:
            refund_result = post_refund(order_id, items, reason)
    except Exception as e:
        logging.error("Error processing refund for order %s: %s", order_id, e)

    if refund_result:
        call.hangup(
            final_instructions=(
                f"Tell the caller their refund for order #{order_id} has been successfully submitted. "
                f"The reason recorded is '{reason}'. "
                "Let them know they should receive a confirmation email and that refunds "
                "typically appear within 5-7 business days. Thank them for their patience."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Apologize and tell the caller that while their order #{order_id} is eligible "
                "for a refund, there was an error submitting it automatically. "
                "Assure them their request has been noted and a support agent will follow up "
                "within one business day. Be sincere and helpful."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])

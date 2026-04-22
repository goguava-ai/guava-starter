import guava
import os
import logging
from guava import logging_utils
import json
import requests
from datetime import datetime, timezone


MAGENTO_BASE_URL = os.environ["MAGENTO_BASE_URL"]
MAGENTO_ACCESS_TOKEN = os.environ["MAGENTO_ACCESS_TOKEN"]

HEADERS = {
    "Authorization": f"Bearer {MAGENTO_ACCESS_TOKEN}",
    "Content-Type": "application/json",
}
REST_BASE = f"{MAGENTO_BASE_URL}/rest/V1"


def get_order_by_increment_id(increment_id: str) -> dict | None:
    resp = requests.get(
        f"{REST_BASE}/orders",
        headers=HEADERS,
        params={
            "searchCriteria[filter_groups][0][filters][0][field]": "increment_id",
            "searchCriteria[filter_groups][0][filters][0][value]": increment_id,
            "searchCriteria[filter_groups][0][filters][0][condition_type]": "eq",
            "searchCriteria[pageSize]": "1",
        },
        timeout=10,
    )
    resp.raise_for_status()
    items = resp.json().get("items", [])
    return items[0] if items else None


def create_rma(order_id: int, order_increment_id: str, customer_name: str, reason: str, items: list) -> dict:
    """Creates a Return Merchandise Authorization (RMA) in Magento."""
    payload = {
        "rmaDataObject": {
            "order_id": order_id,
            "order_increment_id": order_increment_id,
            "customer_name": customer_name,
            "reason": reason,
            "status": "pending",
            "items": items,
        }
    }
    resp = requests.post(
        f"{REST_BASE}/returns",
        headers=HEADERS,
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


agent = guava.Agent(
    name="Casey",
    organization="Prestige Home Goods",
    purpose=(
        "to help customers start a return or exchange for items purchased from "
        "Prestige Home Goods"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "collect_return_info",
        objective=(
            "A customer wants to return or exchange an item. Collect their order number, "
            "which items they're returning, and the reason."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling Prestige Home Goods. I'm Casey, and I can help "
                "you start a return or exchange today."
            ),
            guava.Field(
                key="order_number",
                field_type="text",
                description=(
                    "Ask for their order number. It's printed on their packing slip "
                    "and in their order confirmation email, and starts with a #."
                ),
                required=True,
            ),
            guava.Field(
                key="customer_name",
                field_type="text",
                description="Ask for the name the order was placed under.",
                required=True,
            ),
            guava.Field(
                key="return_type",
                field_type="multiple_choice",
                description="Ask whether they would like a return for a refund or an exchange.",
                choices=["return for refund", "exchange for different item"],
                required=True,
            ),
            guava.Field(
                key="item_description",
                field_type="text",
                description=(
                    "Ask them to describe the item(s) they want to return or exchange. "
                    "Capture product name or SKU if they have it."
                ),
                required=True,
            ),
            guava.Field(
                key="return_reason",
                field_type="multiple_choice",
                description="Ask the reason for the return.",
                choices=[
                    "defective or damaged",
                    "wrong item received",
                    "doesn't match description",
                    "changed my mind",
                    "arrived too late",
                    "other",
                ],
                required=True,
            ),
            guava.Field(
                key="condition",
                field_type="multiple_choice",
                description="Ask about the condition of the item being returned.",
                choices=["unopened", "opened but unused", "used"],
                required=True,
            ),
        ],
    )


@agent.on_task_complete("collect_return_info")
def create_return(call: guava.Call) -> None:
    order_number = (call.get_field("order_number") or "").lstrip("#").strip()
    customer_name = call.get_field("customer_name")
    return_type = call.get_field("return_type")
    item_description = call.get_field("item_description")
    return_reason = call.get_field("return_reason")
    condition = call.get_field("condition")

    logging.info(
        "Return request from %s for order %s — reason: %s, item: %s",
        customer_name, order_number, return_reason, item_description,
    )

    try:
        order = get_order_by_increment_id(order_number)
    except Exception as e:
        logging.error("Failed to look up order %s: %s", order_number, e)
        order = None

    if not order:
        call.hangup(
            final_instructions=(
                f"Let {customer_name} know we couldn't find order #{order_number}. "
                "Ask them to double-check the order number from their confirmation email. "
                "Offer to transfer them to a customer service agent for further help. "
                "Apologize for the inconvenience."
            )
        )
        return

    order_status = order.get("status", "")
    if order_status in ("pending", "processing"):
        call.hangup(
            final_instructions=(
                f"Let {customer_name} know that order #{order_number} is still being "
                "processed and cannot be returned yet. Ask them to wait until it ships "
                "and is delivered, then call back to initiate the return. "
                "Thank them for their patience."
            )
        )
        return

    order_id = order.get("entity_id")
    if order_id is None:
        call.hangup(
            final_instructions=(
                f"Apologize to {customer_name} — there was an issue looking up that order. "
                "Ask them to contact customer service for further assistance."
            )
        )
        return
    order_items = order.get("items", [])
    # Build return item list — use the first matching item or all items
    rma_items = []
    for item in order_items:
        if item.get("product_type") == "simple":
            rma_items.append({
                "order_item_id": item.get("item_id"),
                "qty": 1,
                "reason": return_reason,
                "condition": condition,
            })
    if not rma_items and order_items:
        first = order_items[0]
        rma_items = [{
            "order_item_id": first.get("item_id"),
            "qty": 1,
            "reason": return_reason,
            "condition": condition,
        }]

    reason_text = f"{return_reason} — {item_description}"

    try:
        rma = create_rma(
            order_id=order_id,
            order_increment_id=order_number,
            customer_name=customer_name,
            reason=reason_text,
            items=rma_items,
        )
        rma_id = rma.get("entity_id") or rma.get("increment_id", "")
        logging.info("RMA created: %s for order %s", rma_id, order_number)

        outcome = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": "Casey",
            "use_case": "return_request",
            "order_number": order_number,
            "customer_name": customer_name,
            "return_type": return_type,
            "item_description": item_description,
            "return_reason": return_reason,
            "rma_id": str(rma_id),
        }
        print(json.dumps(outcome, indent=2))

        if return_type == "return for refund":
            call.hangup(
                final_instructions=(
                    f"Let {customer_name} know their return has been approved. "
                    f"Their return number is {rma_id}. "
                    "Let them know they'll receive a prepaid return shipping label by email "
                    "within one business day. Once we receive the item, the refund will be "
                    "processed within 5 to 7 business days to their original payment method. "
                    "Thank them for shopping with Prestige Home Goods."
                )
            )
        else:
            call.hangup(
                final_instructions=(
                    f"Let {customer_name} know their exchange request has been logged. "
                    f"Their return number is {rma_id}. "
                    "Let them know a customer service representative will follow up by email "
                    "within one business day with instructions for sending back the item "
                    "and to confirm the replacement. Thank them for shopping with Prestige Home Goods."
                )
            )
    except Exception as e:
        logging.error("Failed to create RMA for order %s: %s", order_number, e)
        call.hangup(
            final_instructions=(
                f"Apologize to {customer_name} for a technical issue and let them know "
                "we were unable to complete the return request right now. A customer service "
                "agent will follow up by email within one business day to process the return. "
                "Thank them for their patience."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])

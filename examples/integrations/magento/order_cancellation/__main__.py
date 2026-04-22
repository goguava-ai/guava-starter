import json
import logging
import os
from datetime import datetime, timezone

import guava
import requests
from guava import logging_utils

MAGENTO_BASE_URL = os.environ["MAGENTO_BASE_URL"]
MAGENTO_ACCESS_TOKEN = os.environ["MAGENTO_ACCESS_TOKEN"]

HEADERS = {
    "Authorization": f"Bearer {MAGENTO_ACCESS_TOKEN}",
    "Content-Type": "application/json",
}
REST_BASE = f"{MAGENTO_BASE_URL}/rest/V1"

# Orders in these statuses cannot be canceled after this point
NON_CANCELABLE_STATUSES = {"complete", "closed", "canceled"}
# Orders in these statuses may already be in fulfillment
FULFILLMENT_STATUSES = {"processing"}


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


def cancel_order(order_id: int) -> bool:
    """Cancels the order. Returns True on success."""
    resp = requests.post(
        f"{REST_BASE}/orders/{order_id}/cancel",
        headers=HEADERS,
        timeout=10,
    )
    if resp.status_code in (200, 201):
        return resp.json() is True or resp.json() == "true" or resp.status_code == 200
    return False


agent = guava.Agent(
    name="Jordan",
    organization="Prestige Home Goods",
    purpose="to help customers cancel orders that have not yet shipped",
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "collect_cancellation_info",
        objective=(
            "A customer wants to cancel an order. Verify the order, confirm their intent, "
            "and cancel it if still eligible."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling Prestige Home Goods. I'm Jordan. "
                "I can help you cancel an order."
            ),
            guava.Field(
                key="order_number",
                field_type="text",
                description=(
                    "Ask for the order number they'd like to cancel. "
                    "It starts with a # and is in their order confirmation email."
                ),
                required=True,
            ),
            guava.Field(
                key="caller_name",
                field_type="text",
                description="Ask for the name the order was placed under to verify identity.",
                required=True,
            ),
            guava.Field(
                key="cancellation_reason",
                field_type="multiple_choice",
                description="Ask the reason for the cancellation.",
                choices=[
                    "ordered by mistake",
                    "found a better price elsewhere",
                    "changed my mind",
                    "item no longer needed",
                    "delivery time too long",
                    "other",
                ],
                required=True,
            ),
        ],
    )


@agent.on_task_complete("collect_cancellation_info")
def verify_and_cancel(call: guava.Call) -> None:
    order_number = (call.get_field("order_number") or "").lstrip("#").strip()
    caller_name = call.get_field("caller_name")
    cancel_reason = call.get_field("cancellation_reason")

    logging.info(
        "Cancellation request from %s for order %s — reason: %s",
        caller_name, order_number, cancel_reason,
    )

    try:
        order = get_order_by_increment_id(order_number)
    except Exception as e:
        logging.error("Order lookup failed for %s: %s", order_number, e)
        order = None

    if not order:
        call.hangup(
            final_instructions=(
                f"Let {caller_name} know we couldn't find order #{order_number}. "
                "Ask them to check their confirmation email for the correct order number. "
                "Apologize for the inconvenience and offer to transfer them to a "
                "customer service representative. Thank them for calling."
            )
        )
        return

    order_status = order.get("status", "")
    order_id = order.get("entity_id")
    customer_name_on_order = (
        f"{order.get('customer_firstname', '')} {order.get('customer_lastname', '')}"
    ).strip()
    grand_total = order.get("grand_total", "")
    currency = order.get("order_currency_code", "USD")

    if order_status in NON_CANCELABLE_STATUSES:
        status_map = {
            "complete": "already been delivered",
            "closed": "already been closed",
            "canceled": "already been canceled",
        }
        reason = status_map.get(order_status, f"in '{order_status}' status")
        call.hangup(
            final_instructions=(
                f"Let {caller_name} know that order #{order_number} has {reason} "
                "and cannot be canceled. "
                "If the order is complete and they'd like a return, offer to help them "
                "start a return. Thank them for calling Prestige Home Goods."
            )
        )
        return

    if order_status in FULFILLMENT_STATUSES:
        # Order may already be picked — attempt cancel but warn the customer
        logging.info("Order %s is in '%s' status — attempting cancel", order_number, order_status)

    call.set_variable("order_id", order_id)
    call.set_variable("order_number", order_number)
    call.set_variable("caller_name", caller_name)
    call.set_variable("grand_total", grand_total)
    call.set_variable("currency", currency)
    call.set_variable("cancel_reason", cancel_reason)
    call.set_variable("order_status", order_status)

    call.set_task(
        "confirm_cancellation",
        objective=(
            f"Order #{order_number} for ${grand_total} {currency} is eligible for cancellation. "
            f"Confirm with {caller_name} before proceeding."
        ),
        checklist=[
            guava.Field(
                key="cancellation_confirmed",
                field_type="multiple_choice",
                description=(
                    f"Read back: 'I found order #{order_number} for ${grand_total} {currency}. "
                    "Are you sure you'd like to cancel this order?' Capture their response."
                ),
                choices=["yes, cancel it", "no, keep the order"],
                required=True,
            ),
        ],
    )


@agent.on_task_complete("confirm_cancellation")
def execute_cancellation(call: guava.Call) -> None:
    confirmed = call.get_field("cancellation_confirmed")
    order_id = call.get_variable("order_id")
    order_number = call.get_variable("order_number")
    caller_name = call.get_variable("caller_name")
    grand_total = call.get_variable("grand_total")
    currency = call.get_variable("currency")
    cancel_reason = call.get_variable("cancel_reason")
    order_status = call.get_variable("order_status")

    if confirmed != "yes, cancel it":
        call.hangup(
            final_instructions=(
                f"Let {caller_name} know that we've kept their order and no changes "
                "were made. Thank them for calling Prestige Home Goods and wish them "
                "a great day."
            )
        )
        return

    try:
        success = cancel_order(order_id)
    except Exception as e:
        logging.error("Cancel API call failed for order %s: %s", order_number, e)
        success = False

    outcome = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": "Jordan",
        "use_case": "order_cancellation",
        "order_number": order_number,
        "order_id": order_id,
        "caller_name": caller_name,
        "cancel_reason": cancel_reason,
        "success": success,
    }
    print(json.dumps(outcome, indent=2))

    if success:
        logging.info("Order %s canceled successfully", order_number)
        call.hangup(
            final_instructions=(
                f"Let {caller_name} know that order #{order_number} has been successfully "
                f"canceled. If payment was charged, a refund of ${grand_total} {currency} "
                "will be processed to their original payment method within 5 to 7 business "
                "days. They'll also receive a cancellation confirmation email. "
                "Thank them for calling Prestige Home Goods."
            )
        )
    else:
        logging.warning("Order %s cancellation returned failure", order_number)
        in_fulfillment = order_status in FULFILLMENT_STATUSES
        extra = (
            " This may be because the order has already entered fulfillment. "
            if in_fulfillment
            else " "
        )
        call.hangup(
            final_instructions=(
                f"Apologize to {caller_name} and let them know we were unable to cancel "
                f"order #{order_number} automatically.{extra}"
                "Let them know our customer service team will look into it and follow up "
                "by email within one business day. Thank them for their patience."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])

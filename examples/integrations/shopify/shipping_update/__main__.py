import argparse
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


def get_order(order_id: int) -> dict | None:
    resp = requests.get(f"{BASE_URL}/orders/{order_id}.json", headers=get_headers(), timeout=10)
    resp.raise_for_status()
    return resp.json().get("order")


def get_fulfillment_tracking(order: dict) -> list[dict]:
    tracking_info = []
    for fulfillment in order.get("fulfillments", []):
        company = fulfillment.get("tracking_company", "")
        numbers = fulfillment.get("tracking_numbers", [])
        urls = fulfillment.get("tracking_urls", [])
        status = fulfillment.get("shipment_status", fulfillment.get("status", ""))
        tracking_info.append({
            "company": company,
            "numbers": numbers,
            "urls": urls,
            "status": status,
        })
    return tracking_info


agent = guava.Agent(
    name="Casey",
    organization="Kestrel Goods",
    purpose="to provide Kestrel Goods customers with shipping updates on their orders",
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    order_id = int(call.get_variable("order_id"))

    call.set_variable("order", None)
    call.set_variable("tracking", [])
    try:
        order_data = get_order(order_id)
        call.set_variable("order", order_data)
        if order_data:
            call.set_variable("tracking", get_fulfillment_tracking(order_data))
        logging.info("Loaded order %s for shipping update", order_id)
    except Exception as e:
        logging.error("Failed to load order: %s", e)

    order = call.get_variable("order")
    tracking = call.get_variable("tracking")

    if order and tracking:
        t = tracking[0]
        status = t["status"] or order.get("fulfillment_status", "unknown")
        company = t["company"] or "carrier"
        tracking_num = t["numbers"][0] if t["numbers"] else "N/A"
        context = (
            f"Order #{order.get('order_number', order_id)} is {status} via {company}. "
            f"Tracking number: {tracking_num}."
        )
    elif order:
        status = order.get("fulfillment_status", "unfulfilled")
        context = f"Order #{order.get('order_number', order_id)} status is {status} with no tracking yet."
    else:
        context = f"Order {order_id} could not be loaded."

    call.reach_person(contact_full_name=customer_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    customer_name = call.get_variable("customer_name")
    order_id = call.get_variable("order_id")
    order = call.get_variable("order")
    tracking = call.get_variable("tracking")

    if order and tracking:
        t = tracking[0]
        status = t["status"] or order.get("fulfillment_status", "unknown")
        company = t["company"] or "carrier"
        tracking_num = t["numbers"][0] if t["numbers"] else "N/A"
        context = (
            f"Order #{order.get('order_number', order_id)} is {status} via {company}. "
            f"Tracking number: {tracking_num}."
        )
    elif order:
        status = order.get("fulfillment_status", "unfulfilled")
        context = f"Order #{order.get('order_number', order_id)} status is {status} with no tracking yet."
    else:
        context = f"Order {order_id} could not be loaded."

    if outcome == "unavailable":
        call.hangup(
            final_instructions=(
                f"Leave a brief voicemail for {customer_name} from Kestrel Goods with their shipping update. "
                f"{context} Ask them to call back or email support@kestrelgoods.com if they have questions."
            )
        )
    elif outcome == "available":
        call.set_task(
            "handle_shipping_update",
            objective=(
                f"You are calling {customer_name} with a shipping update for their Kestrel Goods order. "
                f"{context} Share the update and answer any questions they have."
            ),
            checklist=[
                guava.Say(
                    f"Hi, may I speak with {customer_name}? "
                    "This is Casey calling from Kestrel Goods with an update on your order."
                ),
                guava.Field(
                    key="questions",
                    field_type="text",
                    description=(
                        "Share the shipping status and tracking number. "
                        "Ask if they have any questions about their delivery."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="issue",
                    field_type="multiple_choice",
                    description="Ask if everything looks good or if there's an issue with their order.",
                    choices=["all good", "package missing", "item damaged", "wrong item", "other issue"],
                    required=True,
                ),
            ],
        )


@agent.on_task_complete("handle_shipping_update")
def on_done(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    order_id = call.get_variable("order_id")
    order = call.get_variable("order")
    tracking = call.get_variable("tracking")

    issue = call.get_field("issue") or "all good"
    questions = call.get_field("questions") or ""

    order_num = order.get("order_number", order_id) if order else order_id
    tracking_url = tracking[0]["urls"][0] if tracking and tracking[0]["urls"] else ""

    if issue == "all good":
        call.hangup(
            final_instructions=(
                f"Thank {customer_name} for their time. "
                + (f"They can track their package at: {tracking_url}. " if tracking_url else "")
                + "Wish them a great day and thank them for shopping with Kestrel Goods."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Apologize for the issue with order #{order_num}. "
                f"The customer reported: {issue}. "
                "Let them know a member of the support team will follow up within one business day "
                "to resolve the issue. Ask them to email support@kestrelgoods.com if they need faster help. "
                "Thank them for their patience."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser()
    parser.add_argument("--order-id", required=True, type=int, help="Shopify order ID")
    parser.add_argument("--customer-name", required=True, help="Customer's first name")
    parser.add_argument("--phone", required=True, help="Customer phone number to call")
    args = parser.parse_args()

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "order_id": str(args.order_id),
            "customer_name": args.customer_name,
        },
    )

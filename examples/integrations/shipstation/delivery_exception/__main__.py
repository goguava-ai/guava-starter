import argparse
import base64
import logging
import os

import guava
import requests
from guava import logging_utils

API_KEY = os.environ["SHIPSTATION_API_KEY"]
API_SECRET = os.environ["SHIPSTATION_API_SECRET"]
BASE_URL = "https://ssapi.shipstation.com"

credentials = base64.b64encode(f"{API_KEY}:{API_SECRET}".encode()).decode()
HEADERS = {
    "Authorization": f"Basic {credentials}",
    "Content-Type": "application/json",
}


def fetch_shipment_by_order_number(order_number: str) -> dict | None:
    resp = requests.get(
        f"{BASE_URL}/shipments",
        headers=HEADERS,
        params={"orderNumber": order_number, "sortBy": "ShipDate", "sortDir": "DESC", "pageSize": "1"},
        timeout=10,
    )
    resp.raise_for_status()
    shipments = resp.json().get("shipments", [])
    return shipments[0] if shipments else None


def fetch_order_by_number(order_number: str) -> dict | None:
    resp = requests.get(
        f"{BASE_URL}/orders",
        headers=HEADERS,
        params={"orderNumber": order_number, "sortBy": "OrderDate", "sortDir": "DESC", "pageSize": "1"},
        timeout=10,
    )
    resp.raise_for_status()
    orders = resp.json().get("orders", [])
    return orders[0] if orders else None


def add_order_note(order_id: int, existing_notes: str, new_note: str) -> None:
    combined = f"{existing_notes}\n{new_note}".strip() if existing_notes else new_note
    resp = requests.post(
        f"{BASE_URL}/orders/createorder",
        headers=HEADERS,
        json={"orderId": order_id, "internalNotes": combined},
        timeout=10,
    )
    resp.raise_for_status()


agent = guava.Agent(
    name="Casey",
    organization="Pacific Home Goods",
    purpose="to assist customers with delivery issues and find solutions",
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    order_number = call.get_variable("order_number")

    try:
        call.set_variable("shipment", fetch_shipment_by_order_number(order_number))
    except Exception as e:
        logging.error("Pre-fetch shipment failed: %s", e)
        call.set_variable("shipment", None)

    try:
        call.set_variable("order", fetch_order_by_number(order_number))
    except Exception as e:
        logging.error("Pre-fetch order failed: %s", e)
        call.set_variable("order", None)

    call.reach_person(contact_full_name=customer_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    customer_name = call.get_variable("customer_name")
    order_number = call.get_variable("order_number")
    exception_reason = call.get_variable("exception_reason")

    if outcome == "unavailable":
        call.hangup(
            final_instructions=(
                f"Leave a brief, professional voicemail for {customer_name}. "
                f"Mention you are calling from Pacific Home Goods about a delivery exception "
                f"on order #{order_number}. "
                "Ask them to call back at 1-800-555-0192 or visit pacifichomegoods.com to resolve the issue. "
                "Keep it under 30 seconds."
            )
        )
    elif outcome == "available":
        shipment = call.get_variable("shipment")
        tracking_number = shipment.get("trackingNumber", "unknown") if shipment else "unknown"
        carrier_code = shipment.get("carrierCode", "the carrier") if shipment else "the carrier"

        call.set_task(
            "handle_outcome",
            objective=(
                f"Inform {customer_name} about a delivery exception on order #{order_number} "
                f"and collect updated delivery instructions to resolve the issue."
            ),
            checklist=[
                guava.Say(
                    f"Hi, may I speak with {customer_name}? "
                    f"This is Casey calling from Pacific Home Goods regarding your recent order."
                ),
                guava.Say(
                    f"I'm reaching out because we received a delivery exception notice from {carrier_code} "
                    f"for your order #{order_number} with tracking number {tracking_number}. "
                    f"The reason noted was: {exception_reason}. "
                    "We want to make sure your package reaches you as quickly as possible."
                ),
                guava.Field(
                    key="resolution_preference",
                    field_type="multiple_choice",
                    description=(
                        "Ask how the customer would like to resolve the delivery issue. "
                        "Offer three options: redeliver to the same address, update the delivery address, "
                        "or hold the package for pickup at a carrier location."
                    ),
                    choices=["redeliver to same address", "update delivery address", "hold for pickup"],
                    required=True,
                ),
                guava.Field(
                    key="updated_instructions",
                    field_type="text",
                    description=(
                        "If they chose 'update delivery address', ask for the full new address. "
                        "If they chose 'redeliver to same address', ask if there are any special "
                        "delivery instructions (e.g., leave at back door, call on arrival). "
                        "If they chose 'hold for pickup', confirm they understand they'll receive "
                        "details from the carrier — ask if they have any questions."
                    ),
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("handle_outcome")
def on_done(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    order_number = call.get_variable("order_number")
    exception_reason = call.get_variable("exception_reason")

    resolution = call.get_field("resolution_preference")
    instructions = call.get_field("updated_instructions") or "No additional instructions provided."

    order = call.get_variable("order")
    if order:
        order_id = order.get("orderId")
        existing_notes = order.get("internalNotes", "") or ""
        note = (
            f"[DELIVERY EXCEPTION] Reason: {exception_reason}. "
            f"Customer resolution preference: {resolution}. "
            f"Instructions: {instructions}."
        )
        try:
            add_order_note(order_id, existing_notes, note)
            logging.info("Updated internal notes on order %s", order_number)
        except Exception as e:
            logging.error("Failed to update order notes: %s", e)

    call.hangup(
        final_instructions=(
            f"Thank {customer_name} for their time and patience. "
            f"Confirm their chosen resolution: {resolution}. "
            f"Let them know Pacific Home Goods will follow up with the carrier to implement "
            "their preference, and they can expect an update within one business day. "
            "Provide the customer service number (1-800-555-0192) if they have further questions. "
            "Be warm and reassuring."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Call a customer about a shipment delivery exception."
    )
    parser.add_argument("phone", help="Customer phone number in E.164 format (e.g. +15551234567)")
    parser.add_argument("--order-number", required=True, help="ShipStation order number")
    parser.add_argument("--name", required=True, help="Customer full name")
    parser.add_argument(
        "--exception-reason",
        required=True,
        help='Delivery exception reason (e.g. "address not found", "delivery attempted - no access")',
    )
    args = parser.parse_args()

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "customer_name": args.name,
            "order_number": args.order_number,
            "exception_reason": args.exception_reason,
        },
    )

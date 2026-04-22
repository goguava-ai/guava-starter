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


agent = guava.Agent(
    name="Jordan",
    organization="Ridgeline Sports",
    purpose="to help customers track their orders and shipments",
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "handle_complete",
        objective="Help the caller find their order status and tracking information.",
        checklist=[
            guava.Say(
                "Thank you for calling Ridgeline Sports. This is Jordan. "
                "I can help you track your order today."
            ),
            guava.Field(
                key="lookup_method",
                field_type="multiple_choice",
                description="Ask whether the customer has their order number or would prefer to look up by email address.",
                choices=["order number", "email address"],
                required=True,
            ),
            guava.Field(
                key="lookup_value",
                field_type="text",
                description=(
                    "If they chose 'order number', ask for their order number. "
                    "If they chose 'email address', ask for the email address on the order."
                ),
                required=True,
            ),
        ],
    )


@agent.on_task_complete("handle_complete")
def on_done(call: guava.Call) -> None:
    lookup_method = call.get_field("lookup_method")
    lookup_value = call.get_field("lookup_value")

    # Build query params based on lookup method
    if lookup_method == "order number":
        order_params = {"orderNumber": lookup_value}
        shipment_params = {"orderNumber": lookup_value}
    else:
        order_params = {"customerEmail": lookup_value}
        shipment_params = {"recipientEmail": lookup_value}

    order = None
    shipment = None

    # Look up the order
    try:
        resp = requests.get(
            f"{BASE_URL}/orders",
            headers=HEADERS,
            params={**order_params, "sortBy": "OrderDate", "sortDir": "DESC", "pageSize": "1"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        orders = data.get("orders", [])
        order = orders[0] if orders else None
    except Exception as e:
        logging.error("ShipStation orders API error: %s", e)
        order = None

    # Look up the shipment for tracking details
    try:
        resp = requests.get(
            f"{BASE_URL}/shipments",
            headers=HEADERS,
            params={**shipment_params, "sortBy": "ShipDate", "sortDir": "DESC", "pageSize": "1"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        shipments = data.get("shipments", [])
        shipment = shipments[0] if shipments else None
    except Exception as e:
        logging.error("ShipStation shipments API error: %s", e)
        shipment = None

    if order is None and shipment is None:
        call.hangup(
            final_instructions=(
                "Tell the caller you were unable to find any orders matching the information "
                "they provided. Apologize and suggest they double-check their order confirmation "
                "email or contact support at ridgelinesports.com. Be warm and helpful."
            )
        )
        return

    order_status = order.get("orderStatus", "unknown") if order else "unknown"
    order_number = order.get("orderNumber", "unknown") if order else "unknown"
    tracking_number = shipment.get("trackingNumber") if shipment else None
    carrier_code = shipment.get("carrierCode") if shipment else None
    ship_date = shipment.get("shipDate") if shipment else None

    call.hangup(
        final_instructions=(
            f"Tell the caller the status of their order. Here are the details: "
            f"Order number: {order_number}. "
            f"Order status: {order_status}. "
            f"Carrier: {carrier_code or 'not yet assigned'}. "
            f"Tracking number: {tracking_number or 'not yet available'}. "
            f"Ship date: {ship_date or 'not yet shipped'}. "
            "Translate the technical order status into plain English (e.g., 'awaiting_shipment' "
            "means 'your order is packed and ready to ship'). "
            "If there is a tracking number, tell them they can use it on the carrier's website. "
            "Thank them for shopping with Ridgeline Sports."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])

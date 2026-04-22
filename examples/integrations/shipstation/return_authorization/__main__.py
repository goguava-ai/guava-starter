import guava
import os
import logging
from guava import logging_utils
import requests
import base64
from datetime import datetime, timedelta, timezone


API_KEY = os.environ["SHIPSTATION_API_KEY"]
API_SECRET = os.environ["SHIPSTATION_API_SECRET"]
BASE_URL = "https://ssapi.shipstation.com"

credentials = base64.b64encode(f"{API_KEY}:{API_SECRET}".encode()).decode()
HEADERS = {
    "Authorization": f"Basic {credentials}",
    "Content-Type": "application/json",
}

# Return window in days
RETURN_WINDOW_DAYS = 30

# Warehouse to ship returns back to (set to your ShipStation warehouse ID)
RETURN_TO_WAREHOUSE_ID = int(os.environ.get("SHIPSTATION_WAREHOUSE_ID", "0"))


def fetch_order(order_number: str) -> dict | None:
    resp = requests.get(
        f"{BASE_URL}/orders",
        headers=HEADERS,
        params={"orderNumber": order_number, "sortBy": "OrderDate", "sortDir": "DESC", "pageSize": "1"},
        timeout=10,
    )
    resp.raise_for_status()
    orders = resp.json().get("orders", [])
    return orders[0] if orders else None


def is_within_return_window(order: dict) -> bool:
    order_date_str = order.get("orderDate") or order.get("createDate")
    if not order_date_str:
        return False
    # ShipStation returns ISO 8601 timestamps
    order_date = datetime.fromisoformat(order_date_str.replace("Z", "+00:00"))
    cutoff = datetime.now(order_date.tzinfo) - timedelta(days=RETURN_WINDOW_DAYS)
    return order_date >= cutoff


def create_return_label(order: dict, return_reason: str) -> dict | None:
    ship_from = order.get("shipTo", {})
    if not ship_from:
        return None

    # Determine carrier and service from the original shipment if available
    carrier_code = order.get("carrierCode", "stamps_com")
    service_code = order.get("serviceCode", "usps_first_class_mail")

    payload = {
        "carrierCode": carrier_code,
        "serviceCode": service_code,
        "packageCode": "package",
        "confirmation": "none",
        "shipDate": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "weight": {"value": 16, "units": "ounces"},
        "shipFrom": {
            "name": ship_from.get("name", ""),
            "street1": ship_from.get("street1", ""),
            "street2": ship_from.get("street2", ""),
            "city": ship_from.get("city", ""),
            "state": ship_from.get("state", ""),
            "postalCode": ship_from.get("postalCode", ""),
            "country": ship_from.get("country", "US"),
            "phone": ship_from.get("phone", ""),
        },
        "shipTo": {
            "name": "Ridgeline Sports Returns",
            "company": "Ridgeline Sports",
            "street1": "100 Warehouse Blvd",
            "city": "Denver",
            "state": "CO",
            "postalCode": "80201",
            "country": "US",
            "phone": "18005550147",
        },
        "isReturnLabel": True,
        "rmaNumber": f"RMA-{order.get('orderNumber', 'UNKNOWN')}",
    }

    resp = requests.post(
        f"{BASE_URL}/shipments/createlabel",
        headers=HEADERS,
        json=payload,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def add_return_note(order_id: int, existing_notes: str, return_reason: str, tracking_number: str) -> None:
    note = (
        f"[RETURN AUTHORIZED] Reason: {return_reason}. "
        f"Return tracking number: {tracking_number}."
    )
    combined = f"{existing_notes}\n{note}".strip() if existing_notes else note
    resp = requests.post(
        f"{BASE_URL}/orders/createorder",
        headers=HEADERS,
        json={"orderId": order_id, "internalNotes": combined},
        timeout=10,
    )
    resp.raise_for_status()


agent = guava.Agent(
    name="Alex",
    organization="Ridgeline Sports",
    purpose="to help customers initiate returns and receive return shipping labels",
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "handle_complete",
        objective="Help the caller start a return for their order and issue a prepaid return label if eligible.",
        checklist=[
            guava.Say(
                "Thank you for calling Ridgeline Sports. This is Alex. "
                "I can help you with a return today. I just need a couple of quick details."
            ),
            guava.Field(
                key="order_number",
                field_type="text",
                description="Ask the caller for their order number.",
                required=True,
            ),
            guava.Field(
                key="return_reason",
                field_type="multiple_choice",
                description="Ask the caller why they are returning the item.",
                choices=[
                    "wrong size",
                    "wrong item received",
                    "item defective or damaged",
                    "changed my mind",
                    "other",
                ],
                required=True,
            ),
            guava.Field(
                key="return_detail",
                field_type="text",
                description=(
                    "If the reason is 'defective or damaged' or 'other', ask the caller to briefly "
                    "describe the issue. Otherwise this field can be skipped."
                ),
                required=False,
            ),
        ],
    )


@agent.on_task_complete("handle_complete")
def on_done(call: guava.Call) -> None:
    order_number = call.get_field("order_number")
    return_reason = call.get_field("return_reason")
    return_detail = call.get_field("return_detail") or ""

    full_reason = f"{return_reason}: {return_detail}".strip(": ") if return_detail else return_reason

    # Fetch the order
    order = None
    return_label = None
    try:
        order = fetch_order(order_number)
    except Exception as e:
        logging.error("ShipStation orders API error: %s", e)
        order = None

    if order is None:
        call.hangup(
            final_instructions=(
                f"Tell the caller you could not locate an order with number {order_number}. "
                "Apologize and ask them to double-check the number from their confirmation email. "
                "Suggest they try again or visit ridgelinesports.com/returns for help."
            )
        )
        return

    order_status = order.get("orderStatus", "")
    if order_status in ("awaiting_payment", "cancelled"):
        call.hangup(
            final_instructions=(
                f"Tell the caller that order #{order_number} has a status of '{order_status}' "
                "and is not eligible for a return at this time. "
                "If the order is cancelled, explain that nothing was charged. "
                "Offer to connect them with a human agent if they need further assistance."
            )
        )
        return

    if not is_within_return_window(order):
        call.hangup(
            final_instructions=(
                f"Tell the caller that order #{order_number} is outside the {RETURN_WINDOW_DAYS}-day "
                "return window and is not eligible for a standard return. "
                "Apologize and let them know they can reach out to ridgelinesports.com/contact "
                "if they believe there are extenuating circumstances."
            )
        )
        return

    # Create the return label
    try:
        return_label = create_return_label(order, full_reason)
    except Exception as e:
        logging.error("Failed to create return label: %s", e)
        return_label = None

    # Note the return on the order regardless of label creation success
    if return_label:
        tracking_number = return_label.get("trackingNumber", "N/A")
        label_url = return_label.get("labelUrl", "")
        try:
            add_return_note(
                order["orderId"],
                order.get("internalNotes", "") or "",
                full_reason,
                tracking_number,
            )
        except Exception as e:
            logging.error("Failed to add return note: %s", e)

        call.hangup(
            final_instructions=(
                f"Tell the caller their return for order #{order_number} has been approved. "
                f"Their return reason was: {full_reason}. "
                f"A prepaid return shipping label has been created. "
                f"The return tracking number is {tracking_number}. "
                f"Tell them the label will be emailed to the address on their order. "
                f"{'The label can also be downloaded at: ' + label_url if label_url else ''} "
                "Ask them to pack the item securely and drop it off at any carrier location. "
                "Confirm that once received, refunds are processed within 5-7 business days. "
                "Thank them for shopping with Ridgeline Sports."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Tell the caller their return for order #{order_number} has been approved "
                "but there was a technical issue generating their prepaid label at this moment. "
                "Apologize for the inconvenience and ask them to visit ridgelinesports.com/returns "
                "or call back so a team member can send the label manually. "
                "Be apologetic and helpful."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])

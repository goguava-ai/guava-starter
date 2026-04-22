import guava
import os
import logging
from guava import logging_utils
import requests
from datetime import datetime


BASE_URL = "https://ssapi.shipstation.com"
AUTH = (os.environ["SHIPSTATION_API_KEY"], os.environ["SHIPSTATION_API_SECRET"])

TRACKING_URLS = {
    "ups": "https://www.ups.com/track?tracknum={tracking_number}",
    "usps": "https://tools.usps.com/go/TrackConfirmAction?tLabels={tracking_number}",
    "fedex": "https://www.fedex.com/fedextrack/?trknbr={tracking_number}",
    "dhl_express": "https://www.dhl.com/en/express/tracking.html?AWB={tracking_number}",
}

ORDER_STATUS_MESSAGES = {
    "awaiting_shipment": "your order is being prepared for shipment",
    "shipped": "your order has shipped",
    "delivered": "your order has been delivered",
    "cancelled": "your order has been cancelled",
    "on_hold": "your order is currently on hold",
}


def get_tracking_url(carrier_code: str, tracking_number: str) -> str:
    template = TRACKING_URLS.get(carrier_code.lower(), "")
    if template:
        return template.format(tracking_number=tracking_number)
    return ""


agent = guava.Agent(
    name="Jordan",
    organization="Coastal Supply Co.",
    purpose="to help Coastal Supply Co. customers track and manage their shipments",
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "lookup_shipment",
        objective=(
            "A customer has called Coastal Supply Co. to track their shipment. "
            "Greet them, collect their order number or email address, look up the shipment, "
            "and give them a full status update including the tracking number and tracking link."
        ),
        checklist=[
            guava.Say(
                "Thanks for calling Coastal Supply Co.! I'm Jordan, and I'm here to help "
                "with your shipment. I'll pull up your order right away."
            ),
            guava.Field(
                key="order_number",
                field_type="text",
                description=(
                    "Ask for their order number. "
                    "If they don't have the order number, ask for their email address instead — "
                    "capture whichever they provide."
                ),
                required=True,
            ),
            guava.Field(
                key="email",
                field_type="text",
                description=(
                    "If they provided an email address instead of an order number in the previous "
                    "step, confirm it here. Skip this field if they already gave an order number."
                ),
                required=False,
            ),
        ],
    )


@agent.on_task_complete("lookup_shipment")
def on_lookup_shipment_done(call: guava.Call) -> None:
    order_number = call.get_field("order_number")
    email = call.get_field("email")

    order = None

    # Try to find the order by order number first; fall back to email lookup.
    try:
        if order_number and "@" not in order_number:
            resp = requests.get(
                f"{BASE_URL}/orders",
                auth=AUTH,
                params={"orderNumber": order_number},
                timeout=10,
            )
            resp.raise_for_status()
            orders = resp.json().get("orders", [])
            if orders:
                order = orders[0]
        else:
            # order_number field contained an email, or caller provided email field
            lookup_email = email or order_number
            resp = requests.get(
                f"{BASE_URL}/orders",
                auth=AUTH,
                params={"customerEmail": lookup_email, "orderStatus": "shipped"},
                timeout=10,
            )
            resp.raise_for_status()
            orders = resp.json().get("orders", [])
            if orders:
                # Take the most recent shipped order
                order = orders[0]
    except Exception as e:
        logging.error("Failed to look up order in ShipStation: %s", e)

    if not order:
        call.hangup(
            final_instructions=(
                "Apologize and let the customer know we weren't able to find an order matching "
                "the information they provided. Ask them to double-check their order number or "
                "email and try again, or visit coastalsupply.com to look up their order online. "
                "Thank them for calling Coastal Supply Co."
            )
        )
        return

    order_id = order.get("orderId")
    order_num_display = order.get("orderNumber", order_number)
    order_status = order.get("orderStatus", "")
    status_message = ORDER_STATUS_MESSAGES.get(order_status, f"in status {order_status}")
    ship_to = order.get("shipTo", {})
    ship_name = ship_to.get("name", "")

    # Fetch the shipment record for this order to get tracking details.
    shipment = None
    try:
        resp = requests.get(
            f"{BASE_URL}/shipments",
            auth=AUTH,
            params={"orderId": order_id},
            timeout=10,
        )
        resp.raise_for_status()
        shipments = resp.json().get("shipments", [])
        # Filter out voided shipments and take the most recent active one.
        active = [s for s in shipments if not s.get("voided", False)]
        if active:
            shipment = active[0]
    except Exception as e:
        logging.error("Failed to fetch shipments for order %s: %s", order_id, e)

    if not shipment:
        # We have the order but no shipment record yet.
        call.set_task(
            "handle_followup",
            objective=(
                f"Let the customer know the status of order {order_num_display} and ask "
                "if there is anything else they need help with."
            ),
            checklist=[
                guava.Say(
                    f"I found your order — order {order_num_display} is currently {status_message}. "
                    "It looks like a tracking record hasn't been generated yet, which usually means "
                    "the label is being prepared. You should receive a shipping confirmation email "
                    "with tracking details very soon."
                ),
                guava.Field(
                    key="anything_else",
                    field_type="multiple_choice",
                    description="Ask if there is anything else you can help them with today.",
                    choices=["report a problem with my order", "start a return", "nothing else"],
                    required=True,
                ),
            ],
        )
        return

    tracking_number = shipment.get("trackingNumber", "")
    carrier_code = shipment.get("carrierCode", "")
    service_code = shipment.get("serviceCode", "")
    ship_date_raw = shipment.get("shipDate", "")

    # Format the ship date into a readable string.
    ship_date_display = ship_date_raw
    if ship_date_raw:
        try:
            dt = datetime.fromisoformat(ship_date_raw.replace("Z", "+00:00"))
            ship_date_display = dt.strftime("%B %-d, %Y")
        except (ValueError, AttributeError):
            ship_date_display = ship_date_raw

    tracking_url = get_tracking_url(carrier_code, tracking_number)
    carrier_display = carrier_code.upper().replace("_", " ")

    logging.info(
        "Shipment found for order %s — carrier: %s, tracking: %s",
        order_id,
        carrier_code,
        tracking_number,
    )

    # Build a tracking URL sentence only if we have one.
    url_sentence = ""
    if tracking_url:
        url_sentence = (
            f" You can also track it online at: {tracking_url}"
        )

    call.set_task(
        "handle_followup",
        objective=(
            f"Read back the shipment details for order {order_num_display} and ask "
            "if there is anything else the customer needs."
        ),
        checklist=[
            guava.Say(
                f"Great news — I found your order! Order {order_num_display} is "
                f"currently {status_message}. "
                f"It shipped via {carrier_display} on {ship_date_display}. "
                f"Your tracking number is {tracking_number}.{url_sentence}"
            ),
            guava.Field(
                key="anything_else",
                field_type="multiple_choice",
                description="Ask if there is anything else you can help them with today.",
                choices=["report a problem with my order", "start a return", "nothing else"],
                required=True,
            ),
        ],
    )


@agent.on_task_complete("handle_followup")
def on_followup_done(call: guava.Call) -> None:
    choice = call.get_field("anything_else") or "nothing else"

    if "problem" in choice.lower():
        call.hangup(
            final_instructions=(
                "Let the customer know you're transferring their concern to our support team. "
                "Ask them to call back and say they'd like to report a shipping problem, or "
                "they can email support@coastalsupply.com with their order number and a brief "
                "description. Thank them for calling Coastal Supply Co."
            )
        )
    elif "return" in choice.lower():
        call.hangup(
            final_instructions=(
                "Let the customer know they can start a return by calling back and asking for "
                "our returns team, or by visiting coastalsupply.com/returns. "
                "Thank them for calling Coastal Supply Co. and wish them a great day."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                "Thank the customer for calling Coastal Supply Co. and wish them a great day. "
                "Let them know we're always here if they need anything."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])

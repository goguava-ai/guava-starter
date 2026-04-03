import guava
import os
import logging
import requests

logging.basicConfig(level=logging.INFO)

STORE_HASH = os.environ["BIGCOMMERCE_STORE_HASH"]
ACCESS_TOKEN = os.environ["BIGCOMMERCE_ACCESS_TOKEN"]
BASE_V2 = f"https://api.bigcommerce.com/stores/{STORE_HASH}/v2"
BASE_V3 = f"https://api.bigcommerce.com/stores/{STORE_HASH}/v3"

HEADERS = {
    "X-Auth-Token": ACCESS_TOKEN,
    "Content-Type": "application/json",
    "Accept": "application/json",
}


def fetch_customer_by_email(email: str):
    resp = requests.get(
        f"{BASE_V3}/customers",
        headers=HEADERS,
        params={"email:in": email},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json().get("data", [])
    return data[0] if data else None


def fetch_recent_order(customer_id: int):
    resp = requests.get(
        f"{BASE_V2}/orders",
        headers=HEADERS,
        params={"customer_id": customer_id, "limit": 1, "sort": "id:desc"},
        timeout=10,
    )
    resp.raise_for_status()
    orders = resp.json()
    return orders[0] if orders else None


def fetch_shipments(order_id: int):
    resp = requests.get(
        f"{BASE_V2}/orders/{order_id}/shipments",
        headers=HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


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


class OrderStatusController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Crestline Outdoor Gear",
            agent_name="Sierra",
            agent_purpose="to help customers check on their order status and tracking information",
        )

        self.set_task(
            objective=(
                "Look up the caller's most recent order using their email address "
                "and give them a clear update on its status, including tracking "
                "information if available."
            ),
            checklist=[
                guava.Say(
                    "Hi, thanks for calling Crestline Outdoor Gear! My name is Sierra. "
                    "I can pull up your order status right away."
                ),
                guava.Field(
                    key="email",
                    field_type="email",
                    description="Ask the caller for the email address on their account.",
                    required=True,
                ),
            ],
            on_complete=self.handle_complete,
        )

        self.accept_call()

    def handle_complete(self):
        email = self.get_field("email")

        order = None
        shipments = []
        status_label = "unknown"

        try:
            customer = fetch_customer_by_email(email)
            if customer:
                order = fetch_recent_order(customer["id"])
                if order:
                    status_id = order.get("status_id")
                    status_label = ORDER_STATUSES.get(status_id, f"status {status_id}")
                    try:
                        shipments = fetch_shipments(order["id"])
                        if not isinstance(shipments, list):
                            shipments = []
                    except Exception as e:
                        logging.warning("Could not fetch shipments for order %s: %s", order["id"], e)
            else:
                logging.info("No customer found for email: %s", email)
        except Exception as e:
            logging.error("BigCommerce API error during order status lookup: %s", e)

        if order is None:
            self.hangup(
                final_instructions=(
                    f"No account or orders were found for the email address {email}. "
                    "Apologize and suggest the caller verify their email or contact support. "
                    "Be warm and helpful."
                )
            )
            return

        tracking_info = ""
        if shipments:
            first = shipments[0]
            carrier = first.get("shipping_provider", "the carrier")
            tracking_number = first.get("tracking_number", "")
            if tracking_number:
                tracking_info = (
                    f"The tracking number is {tracking_number} with {carrier}."
                )
            else:
                tracking_info = f"The order has been handed to {carrier} but no tracking number is recorded yet."

        self.hangup(
            final_instructions=(
                f"Tell the caller their most recent order (order #{order['id']}, "
                f"placed on {order.get('date_created', 'an unknown date')}) is currently "
                f"'{status_label}'. {tracking_info} "
                "If the order is shipped or completed, encourage them to track it. "
                "If it's awaiting fulfillment or payment, reassure them it's being processed. "
                "Be friendly and concise."
            )
        )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=OrderStatusController,
    )

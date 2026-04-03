import argparse
import guava
import os
import logging
import requests

logging.basicConfig(level=logging.INFO)

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


class ShippingUpdateController(guava.CallController):
    def __init__(self, order_id: int, customer_name: str):
        super().__init__()

        self._order_id = order_id
        self._order: dict | None = None
        self._tracking: list[dict] = []

        try:
            self._order = get_order(order_id)
            if self._order:
                self._tracking = get_fulfillment_tracking(self._order)
            logging.info("Loaded order %s for shipping update", order_id)
        except Exception as e:
            logging.error("Failed to load order: %s", e)

        order = self._order
        tracking = self._tracking

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

        self.set_persona(
            organization_name="Kestrel Goods",
            agent_name="Casey",
            agent_purpose="to provide Kestrel Goods customers with shipping updates on their orders",
        )

        self.set_task(
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
            on_complete=self.handle_shipping_update,
        )

        self.reach_person(customer_name)

    def handle_shipping_update(self):
        issue = self.get_field("issue") or "all good"
        questions = self.get_field("questions") or ""

        order = self._order
        order_num = order.get("order_number", self._order_id) if order else self._order_id
        tracking = self._tracking
        tracking_url = tracking[0]["urls"][0] if tracking and tracking[0]["urls"] else ""

        if issue == "all good":
            self.hangup(
                final_instructions=(
                    f"Thank {self.get_field('questions') or 'the customer'} for their time. "
                    + (f"They can track their package at: {tracking_url}. " if tracking_url else "")
                    + "Wish them a great day and thank them for shopping with Kestrel Goods."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    f"Apologize for the issue with order #{order_num}. "
                    f"The customer reported: {issue}. "
                    "Let them know a member of the support team will follow up within one business day "
                    "to resolve the issue. Ask them to email support@kestrelgoods.com if they need faster help. "
                    "Thank them for their patience."
                )
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--order-id", required=True, type=int, help="Shopify order ID")
    parser.add_argument("--customer-name", required=True, help="Customer's first name")
    parser.add_argument("--phone", required=True, help="Customer phone number to call")
    args = parser.parse_args()

    guava.Client().create_outbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        customer_number=args.phone,
        controller_class=ShippingUpdateController,
        controller_args={
            "order_id": args.order_id,
            "customer_name": args.customer_name,
        },
    )

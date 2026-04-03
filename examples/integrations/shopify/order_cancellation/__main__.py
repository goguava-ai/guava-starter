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


def find_order_by_email(email: str, order_number: str = "") -> dict | None:
    params: dict = {"email": email, "status": "open", "limit": 10}
    resp = requests.get(f"{BASE_URL}/orders.json", headers=get_headers(), params=params, timeout=10)
    resp.raise_for_status()
    orders = resp.json().get("orders", [])
    if order_number:
        num = order_number.lstrip("#")
        orders = [o for o in orders if str(o.get("order_number", "")) == num]
    return orders[0] if orders else None


def cancel_order(order_id: int, reason: str = "customer") -> dict | None:
    payload = {"reason": reason, "email": True, "restock": True}
    resp = requests.post(
        f"{BASE_URL}/orders/{order_id}/cancel.json",
        headers=get_headers(),
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("order")


class OrderCancellationController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Kestrel Goods",
            agent_name="Casey",
            agent_purpose="to help Kestrel Goods customers cancel their orders",
        )

        self.set_task(
            objective=(
                "A customer has called to cancel an order. "
                "Verify their email, find the order, confirm cancellation, and process it if they confirm."
            ),
            checklist=[
                guava.Say(
                    "Thank you for calling Kestrel Goods. This is Casey. I can help you cancel an order today."
                ),
                guava.Field(
                    key="email",
                    field_type="text",
                    description="Ask for the email address on the order.",
                    required=True,
                ),
                guava.Field(
                    key="order_number",
                    field_type="text",
                    description="Ask for the order number if they have it (optional).",
                    required=False,
                ),
                guava.Field(
                    key="cancel_reason",
                    field_type="multiple_choice",
                    description="Ask why they'd like to cancel.",
                    choices=["changed mind", "ordered by mistake", "found better price", "item no longer needed", "other"],
                    required=True,
                ),
                guava.Field(
                    key="confirm_cancel",
                    field_type="multiple_choice",
                    description=(
                        "Find the order and read back the order number and total. "
                        "Ask if they confirm they want to cancel this order."
                    ),
                    choices=["yes", "no"],
                    required=True,
                ),
            ],
            on_complete=self.cancel_order,
        )

        self.accept_call()

    def cancel_order(self):
        email = self.get_field("email") or ""
        order_number = self.get_field("order_number") or ""
        cancel_reason = self.get_field("cancel_reason") or "customer"
        confirm = self.get_field("confirm_cancel") or "no"

        if confirm != "yes":
            self.hangup(
                final_instructions=(
                    "Let the customer know no changes were made to their order. "
                    "If they change their mind, they can call back anytime. Thank them for calling Kestrel Goods."
                )
            )
            return

        reason_map = {
            "changed mind": "customer",
            "ordered by mistake": "customer",
            "found better price": "customer",
            "item no longer needed": "customer",
            "other": "customer",
        }
        plaid_reason = reason_map.get(cancel_reason, "customer")

        order = None
        try:
            order = find_order_by_email(email, order_number)
        except Exception as e:
            logging.error("Failed to find order: %s", e)

        if not order:
            self.hangup(
                final_instructions=(
                    "Let the customer know we couldn't find an open order with that email address. "
                    "If they believe this is an error, they can email support@kestrelgoods.com. "
                    "Thank them for calling."
                )
            )
            return

        order_id = order["id"]
        order_num = order.get("order_number", "")
        total = order.get("total_price", "")

        cancelled = None
        try:
            cancelled = cancel_order(order_id, reason=plaid_reason)
            logging.info("Cancelled Shopify order %s for %s", order_num, email)
        except Exception as e:
            logging.error("Failed to cancel order %s: %s", order_id, e)

        if cancelled:
            self.hangup(
                final_instructions=(
                    f"Let the customer know order #{order_num} (${total}) has been successfully cancelled. "
                    "A confirmation email has been sent to the address on file. "
                    "If they were charged, any refund will appear within 5-7 business days. "
                    "Thank them for calling Kestrel Goods."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    f"Apologize — we were unable to cancel order #{order_num} automatically. "
                    "Ask them to email support@kestrelgoods.com referencing their order number "
                    "and the team will process the cancellation manually. Thank them for their patience."
                )
            )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=OrderCancellationController,
    )

import guava
import os
import logging
from guava import logging_utils
import requests


SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
REST_URL = f"{SUPABASE_URL}/rest/v1"


def get_headers() -> dict:
    service_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    }


def find_orders_by_email(email: str) -> list[dict]:
    # Join users and orders; assumes orders table has user_id FK
    resp = requests.get(
        f"{REST_URL}/orders",
        headers={**get_headers(), "Prefer": ""},
        params={
            "select": "id,order_number,status,total,currency,created_at,shipping_status,tracking_number,users!inner(email)",
            "users.email": f"eq.{email}",
            "order": "created_at.desc",
            "limit": "5",
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def find_order_by_number(order_number: str) -> dict | None:
    resp = requests.get(
        f"{REST_URL}/orders",
        headers={**get_headers(), "Prefer": ""},
        params={
            "order_number": f"eq.{order_number.lstrip('#')}",
            "limit": "1",
        },
        timeout=10,
    )
    resp.raise_for_status()
    rows = resp.json()
    return rows[0] if rows else None


class OrderStatusController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Clearline",
            agent_name="Jamie",
            agent_purpose="to help Clearline customers check the status of their orders",
        )

        self.set_task(
            objective=(
                "A customer has called to check on an order. "
                "Verify their email and optional order number, then read back the order status and tracking information."
            ),
            checklist=[
                guava.Say(
                    "Welcome to Clearline support. This is Jamie. I can help you check on an order."
                ),
                guava.Field(
                    key="email",
                    field_type="text",
                    description="Ask for the email address on the account.",
                    required=True,
                ),
                guava.Field(
                    key="order_number",
                    field_type="text",
                    description="Ask for the order number if they have it (optional).",
                    required=False,
                ),
            ],
            on_complete=self.check_order_status,
        )

        self.accept_call()

    def check_order_status(self):
        email = self.get_field("email") or ""
        order_number = self.get_field("order_number") or ""

        logging.info("Checking order status: email=%s, order_number=%s", email, order_number)

        order = None
        try:
            if order_number:
                order = find_order_by_number(order_number)
            if not order and email:
                orders = find_orders_by_email(email)
                order = orders[0] if orders else None
            logging.info("Order found: %s", order.get("order_number") if order else None)
        except Exception as e:
            logging.error("Failed to look up order: %s", e)

        if not order:
            self.hangup(
                final_instructions=(
                    "Let the customer know we couldn't find an order matching that information. "
                    "Ask them to double-check and call back if needed. "
                    "Thank them for calling Clearline."
                )
            )
            return

        order_num = order.get("order_number", "")
        status = order.get("status", "unknown")
        total = order.get("total", 0)
        currency = order.get("currency", "USD")
        shipping_status = order.get("shipping_status", "")
        tracking = order.get("tracking_number", "")

        details = f"Order #{order_num}: status is {status}, total ${total} {currency}."
        if shipping_status:
            details += f" Shipping: {shipping_status}."
        if tracking:
            details += f" Tracking number: {tracking}."

        self.hangup(
            final_instructions=(
                f"Read the following order details to the customer: {details} "
                "Thank them for calling Clearline."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=OrderStatusController,
    )

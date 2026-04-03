import guava
import os
import logging
import pymysql
import pymysql.cursors

logging.basicConfig(level=logging.INFO)


def get_connection():
    return pymysql.connect(
        host=os.environ["MYSQL_HOST"],
        port=int(os.environ.get("MYSQL_PORT", "3306")),
        user=os.environ["MYSQL_USER"],
        password=os.environ["MYSQL_PASSWORD"],
        database=os.environ["MYSQL_DATABASE"],
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


def get_order(order_number: str) -> dict | None:
    """Fetches an order by its order number. Returns the order row or None."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT order_number, status, total_amount, currency,
                       estimated_delivery, created_at, shipping_address
                FROM orders
                WHERE order_number = %s
                LIMIT 1
                """,
                (order_number,),
            )
            return cursor.fetchone()


def get_order_items(order_number: str) -> list[dict]:
    """Returns the line items for an order."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT oi.product_name, oi.quantity, oi.unit_price
                FROM order_items oi
                JOIN orders o ON oi.order_id = o.id
                WHERE o.order_number = %s
                """,
                (order_number,),
            )
            return cursor.fetchall()


class OrderStatusController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Peak Outdoors",
            agent_name="Riley",
            agent_purpose="to help Peak Outdoors customers check the status of their orders",
        )

        self.set_task(
            objective=(
                "A customer has called to check on their order. "
                "Collect their order number, look it up in the database, "
                "and give them a full status update including items and estimated delivery."
            ),
            checklist=[
                guava.Say(
                    "Thanks for calling Peak Outdoors. I'm Riley. "
                    "I can pull up your order details right now. "
                    "Do you have your order number handy?"
                ),
                guava.Field(
                    key="order_number",
                    field_type="text",
                    description=(
                        "Ask for their order number. It typically starts with 'PO' followed "
                        "by digits (e.g. PO-10482). Capture it exactly as they say it."
                    ),
                    required=True,
                ),
            ],
            on_complete=self.look_up_order,
        )

        self.accept_call()

    def look_up_order(self):
        order_number = (self.get_field("order_number") or "").strip().upper()
        logging.info("Looking up order: %s", order_number)

        try:
            order = get_order(order_number)
        except Exception as e:
            logging.error("Database error looking up order %s: %s", order_number, e)
            order = None

        if not order:
            self.hangup(
                final_instructions=(
                    f"Let the caller know you couldn't find an order with number '{order_number}'. "
                    "Ask them to double-check the number — it should start with 'PO'. "
                    "Offer to transfer them to a live agent if they need further help."
                )
            )
            return

        status = order.get("status", "unknown")
        total = order.get("total_amount")
        currency = (order.get("currency") or "USD").upper()
        delivery = order.get("estimated_delivery")
        delivery_str = delivery.strftime("%B %d, %Y") if delivery else "not yet available"
        total_str = f"${float(total):,.2f} {currency}" if total else ""

        try:
            items = get_order_items(order_number)
        except Exception as e:
            logging.error("Failed to fetch items for order %s: %s", order_number, e)
            items = []

        item_summary = ""
        if items:
            lines = [f"{r['product_name']} ×{r['quantity']}" for r in items]
            item_summary = ", ".join(lines)

        logging.info("Order %s found: status=%s, delivery=%s", order_number, status, delivery_str)

        self.hangup(
            final_instructions=(
                f"Let the caller know their order {order_number} has been found. "
                f"Status: {status}. "
                + (f"Items: {item_summary}. " if item_summary else "")
                + (f"Order total: {total_str}. " if total_str else "")
                + f"Estimated delivery: {delivery_str}. "
                "If the status is 'shipped', let them know it's on its way. "
                "If it's 'processing', let them know it will ship within 1–2 business days."
            )
        )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=OrderStatusController,
    )

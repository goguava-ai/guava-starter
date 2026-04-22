import guava
import os
import logging
from guava import logging_utils
import firebase_admin
from firebase_admin import credentials, firestore


cred = credentials.Certificate(os.environ["GOOGLE_APPLICATION_CREDENTIALS"])
firebase_admin.initialize_app(cred)
db = firestore.client()

ORDERS_COLLECTION = os.environ.get("FIRESTORE_ORDERS_COLLECTION", "orders")

ORDER_STATUS_LABELS = {
    "pending": "has been received and is pending processing",
    "processing": "is currently being processed",
    "packed": "has been packed and is awaiting pickup by the carrier",
    "shipped": "has been shipped and is on its way",
    "out_for_delivery": "is out for delivery today",
    "delivered": "has been delivered",
    "cancelled": "has been cancelled",
    "refunded": "has been refunded",
    "on_hold": "is on hold — our team is reviewing it",
}


def lookup_order_by_id(order_id: str) -> dict | None:
    """Fetch an order document by its document ID or order_number field."""
    # Try direct document ID first
    doc = db.collection(ORDERS_COLLECTION).document(order_id).get()
    if doc.exists:
        data = doc.to_dict()
        data["_id"] = doc.id
        return data

    # Fall back to searching by order_number field
    docs = (
        db.collection(ORDERS_COLLECTION)
        .where("order_number", "==", order_id)
        .limit(1)
        .stream()
    )
    for doc in docs:
        data = doc.to_dict()
        data["_id"] = doc.id
        return data
    return None


def lookup_orders_by_email(email: str, limit: int = 3) -> list[dict]:
    """Return the most recent orders for a given customer email."""
    docs = (
        db.collection(ORDERS_COLLECTION)
        .where("customer_email", "==", email.lower().strip())
        .order_by("created_at", direction=firestore.Query.DESCENDING)
        .limit(limit)
        .stream()
    )
    results = []
    for doc in docs:
        data = doc.to_dict()
        data["_id"] = doc.id
        results.append(data)
    return results


def format_order(order: dict) -> str:
    order_num = order.get("order_number") or order.get("_id", "unknown")
    status = order.get("status", "unknown")
    status_label = ORDER_STATUS_LABELS.get(status, f"in status: {status}")
    items = order.get("items_summary") or order.get("item_count") or ""
    items_note = f" ({items})" if items else ""
    return f"Order #{order_num}{items_note} {status_label}"


class OrderStatusCheckController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Crestline Commerce",
            agent_name="Sam",
            agent_purpose=(
                "to help Crestline Commerce customers check the status of their orders"
            ),
        )

        self.set_task(
            objective=(
                "A customer is calling to check on an order. Look up their order in Firestore "
                "and share the current status."
            ),
            checklist=[
                guava.Say(
                    "Thanks for calling Crestline Commerce. This is Sam. "
                    "I can look up your order right away."
                ),
                guava.Field(
                    key="lookup_method",
                    field_type="multiple_choice",
                    description=(
                        "Ask if they have their order number, or if they'd prefer to "
                        "look up by email address."
                    ),
                    choices=["order number", "email address"],
                    required=True,
                ),
                guava.Field(
                    key="lookup_value",
                    field_type="text",
                    description=(
                        "Ask for their order number or email address, depending on their choice."
                    ),
                    required=True,
                ),
            ],
            on_complete=self.look_up_order,
        )

        self.accept_call()

    def look_up_order(self):
        method = self.get_field("lookup_method") or "order number"
        value = (self.get_field("lookup_value") or "").strip()

        logging.info("Looking up order by %s: %s", method, value)

        try:
            if "email" in method:
                orders = lookup_orders_by_email(value)
            else:
                order = lookup_order_by_id(value)
                orders = [order] if order else []
        except Exception as e:
            logging.error("Firestore order lookup failed: %s", e)
            orders = []

        if not orders:
            self.hangup(
                final_instructions=(
                    "Let the customer know you couldn't find an order matching their information. "
                    "Suggest they double-check their order number from their confirmation email, "
                    "or offer to transfer them to a support agent. Be apologetic and helpful."
                )
            )
            return

        if len(orders) == 1:
            order_summary = format_order(orders[0])
            tracking = orders[0].get("tracking_number") or ""
            tracking_note = (
                f" Their tracking number is {tracking}." if tracking else ""
            )
            logging.info("Order found: %s", orders[0].get("_id"))
            self.hangup(
                final_instructions=(
                    f"Let the customer know: {order_summary}.{tracking_note} "
                    "Be clear and friendly. If the order is delayed or on hold, "
                    "empathize and offer to have a specialist follow up. "
                    "Thank them for calling Crestline Commerce."
                )
            )
        else:
            summaries = "; ".join(format_order(o) for o in orders)
            logging.info("Found %d orders for %s", len(orders), value)
            self.hangup(
                final_instructions=(
                    f"Let the customer know you found {len(orders)} recent orders on their account. "
                    f"Read them the status of each: {summaries}. "
                    "If they have questions about a specific order, encourage them to call back "
                    "with the order number for faster lookup. "
                    "Thank them for calling Crestline Commerce."
                )
            )


if __name__ == "__main__":
    logging_utils.configure_logging()
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=OrderStatusCheckController,
    )

import guava
import os
import logging
import json
import requests
from datetime import datetime

logging.basicConfig(level=logging.INFO)

MAGENTO_BASE_URL = os.environ["MAGENTO_BASE_URL"]  # e.g. https://mystore.com
MAGENTO_ACCESS_TOKEN = os.environ["MAGENTO_ACCESS_TOKEN"]  # Admin integration token

HEADERS = {
    "Authorization": f"Bearer {MAGENTO_ACCESS_TOKEN}",
    "Content-Type": "application/json",
}
REST_BASE = f"{MAGENTO_BASE_URL}/rest/V1"


def search_orders_by_email(email: str) -> list:
    """Returns the 5 most recent orders placed by a customer email."""
    resp = requests.get(
        f"{REST_BASE}/orders",
        headers=HEADERS,
        params={
            "searchCriteria[filter_groups][0][filters][0][field]": "customer_email",
            "searchCriteria[filter_groups][0][filters][0][value]": email,
            "searchCriteria[filter_groups][0][filters][0][condition_type]": "eq",
            "searchCriteria[sortOrders][0][field]": "created_at",
            "searchCriteria[sortOrders][0][direction]": "DESC",
            "searchCriteria[pageSize]": "5",
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("items", [])


def get_order_by_increment_id(increment_id: str) -> dict | None:
    """Looks up a single order by the customer-facing order number (increment ID)."""
    resp = requests.get(
        f"{REST_BASE}/orders",
        headers=HEADERS,
        params={
            "searchCriteria[filter_groups][0][filters][0][field]": "increment_id",
            "searchCriteria[filter_groups][0][filters][0][value]": increment_id,
            "searchCriteria[filter_groups][0][filters][0][condition_type]": "eq",
            "searchCriteria[pageSize]": "1",
        },
        timeout=10,
    )
    resp.raise_for_status()
    items = resp.json().get("items", [])
    return items[0] if items else None


def format_order(order: dict) -> str:
    order_id = order.get("increment_id", "")
    status = order.get("status", "unknown")
    total = order.get("grand_total", "")
    currency = order.get("order_currency_code", "")
    created = order.get("created_at", "")[:10]
    items = order.get("items", [])
    item_names = [i.get("name", "") for i in items if i.get("product_type") != "simple" or True][:2]
    item_note = f" — {', '.join(item_names)}" if item_names else ""
    return f"Order {order_id}: {status}, ${total} {currency}, placed {created}{item_note}"


class OrderStatusController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Prestige Home Goods",
            agent_name="Alex",
            agent_purpose=(
                "to help customers check the status of their online orders"
            ),
        )

        self.set_task(
            objective=(
                "A customer is calling to check on their order. Collect their email or "
                "order number and look up the current status."
            ),
            checklist=[
                guava.Say(
                    "Thank you for calling Prestige Home Goods. I'm Alex, and I can look "
                    "up your order status right now."
                ),
                guava.Field(
                    key="lookup_type",
                    field_type="multiple_choice",
                    description=(
                        "Ask whether they have a specific order number (it starts with a #) "
                        "or if they'd prefer to look up by their email address."
                    ),
                    choices=["order number", "email address"],
                    required=True,
                ),
                guava.Field(
                    key="identifier",
                    field_type="text",
                    description=(
                        "Ask them to provide their order number or email address, "
                        "whichever they selected."
                    ),
                    required=True,
                ),
            ],
            on_complete=self.look_up_order,
        )

        self.accept_call()

    def look_up_order(self):
        lookup_type = self.get_field("lookup_type")
        identifier = (self.get_field("identifier") or "").strip()
        by_order = lookup_type == "order number"

        logging.info("Magento order lookup — type: %s, id: %s", lookup_type, identifier)

        try:
            if by_order:
                # Strip any leading # the customer may have spoken
                clean_id = identifier.lstrip("#").strip()
                order = get_order_by_increment_id(clean_id)
                orders = [order] if order else []
            else:
                orders = search_orders_by_email(identifier)

            result = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "agent": "Alex",
                "use_case": "order_status",
                "lookup_type": lookup_type,
                "identifier": identifier,
                "orders_found": len(orders),
                "orders": [
                    {
                        "increment_id": o.get("increment_id"),
                        "status": o.get("status"),
                        "grand_total": o.get("grand_total"),
                        "currency": o.get("order_currency_code"),
                        "created_at": o.get("created_at"),
                        "shipping_description": o.get("shipping_description"),
                    }
                    for o in orders
                ],
            }
            print(json.dumps(result, indent=2))

            if not orders:
                self.hangup(
                    final_instructions=(
                        f"Let the caller know we couldn't find any orders for "
                        f"{'order number' if by_order else 'email'} {identifier}. "
                        "Ask them to double-check the information and try again, or offer to "
                        "transfer them to a customer service representative. "
                        "Thank them for calling Prestige Home Goods."
                    )
                )
                return

            if by_order:
                order = orders[0]
                summary = format_order(order)
                shipping = order.get("shipping_description", "")
                tracking = ""
                ext = order.get("extension_attributes", {})
                tracks = ext.get("shipping_assignments", [])
                # Tracking numbers are nested in extension attributes
                ship_note = f" Shipping method: {shipping}." if shipping else ""
                status_label = order.get("status", "unknown")
                status_map = {
                    "pending": "pending — we've received your order and are preparing it",
                    "processing": "processing — your order is being prepared for shipment",
                    "complete": "delivered",
                    "closed": "closed",
                    "canceled": "canceled",
                    "holded": "on hold — our team is reviewing it",
                }
                status_readable = status_map.get(status_label, status_label)
                self.hangup(
                    final_instructions=(
                        f"Let the caller know their order is currently {status_readable}.{ship_note} "
                        "If it's processing, let them know they'll receive a shipping confirmation "
                        "email with tracking once it ships. "
                        "Thank them for shopping with Prestige Home Goods."
                    )
                )
            else:
                summaries = [format_order(o) for o in orders[:3]]
                summary_text = "; ".join(summaries)
                self.hangup(
                    final_instructions=(
                        f"Let the caller know we found {len(orders)} recent order(s) on their "
                        f"account. Here is the information: {summary_text}. "
                        "If they want details on a specific order, offer to look it up by order "
                        "number. Thank them for calling Prestige Home Goods."
                    )
                )
        except Exception as e:
            logging.error("Magento order lookup failed: %s", e)
            self.hangup(
                final_instructions=(
                    "Apologize for a technical issue and let the caller know we were unable "
                    "to retrieve their order information right now. A customer service "
                    "representative will follow up shortly. Thank them for their patience."
                )
            )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=OrderStatusController,
    )

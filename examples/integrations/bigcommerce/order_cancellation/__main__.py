import guava
import os
import logging
import json
import requests
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)

STORE_HASH = os.environ["BIGCOMMERCE_STORE_HASH"]
AUTH_TOKEN = os.environ["BIGCOMMERCE_AUTH_TOKEN"]
V2_BASE = f"https://api.bigcommerce.com/stores/{STORE_HASH}/v2"

HEADERS = {
    "X-Auth-Token": AUTH_TOKEN,
    "Content-Type": "application/json",
    "Accept": "application/json",
}

# Orders in these states have not yet shipped and can still be cancelled
CANCELLABLE_STATUS_IDS = {0, 1, 7, 9, 11}

STATUS_MAP = {
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


class OrderCancellationController(guava.CallController):
    def __init__(self):
        super().__init__()
        self.order = None

        self.set_persona(
            organization_name="Harbor House",
            agent_name="Morgan",
            agent_purpose="to help Harbor House customers cancel their orders quickly and without hassle",
        )

        self.set_task(
            objective=(
                "A customer has called Harbor House to cancel an order. "
                "Greet them, collect their email address, order number, and reason for cancellation "
                "so we can locate and process their request."
            ),
            checklist=[
                guava.Say(
                    "Thanks for calling Harbor House. My name is Morgan, and I can help you "
                    "with your cancellation today."
                ),
                guava.Field(
                    key="email",
                    description="Ask for their email address so we can pull up their account.",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="order_number",
                    description=(
                        "Ask for the order number they'd like to cancel. "
                        "Capture it as a plain number."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="cancel_reason",
                    description=(
                        "Ask why they'd like to cancel the order. "
                        "Offer these options: 'ordered by mistake', 'found better price', "
                        "'no longer needed', 'taking too long to ship', 'wrong item ordered'."
                    ),
                    field_type="multiple_choice",
                    choices=[
                        "ordered by mistake",
                        "found better price",
                        "no longer needed",
                        "taking too long to ship",
                        "wrong item ordered",
                    ],
                    required=True,
                ),
            ],
            on_complete=self.verify_order,
        )

        self.accept_call()

    def verify_order(self):
        email = self.get_field("email")
        order_number = self.get_field("order_number")
        cancel_reason = self.get_field("cancel_reason")

        # Look up the order by email to confirm it belongs to this customer
        try:
            resp = requests.get(
                f"{V2_BASE}/orders",
                headers=HEADERS,
                params={"email": email, "sort": "date_created:desc", "limit": 50},
                timeout=10,
            )
            resp.raise_for_status()
            orders = resp.json()
        except Exception as e:
            logging.error("Failed to fetch orders for %s: %s", email, e)
            self.hangup(
                final_instructions=(
                    "Apologize to the customer and let them know we were unable to look up "
                    "their order at this time. Ask them to try again shortly or visit "
                    "harborhouse.com to manage their order. Thank them for calling."
                )
            )
            return

        order = None
        for o in orders:
            if str(o.get("id")) == str(order_number).strip():
                order = o
                break

        if order is None:
            self.hangup(
                final_instructions=(
                    f"Let the customer know that order #{order_number} could not be found "
                    "under the email address they provided. Ask them to double-check both "
                    "the order number and email address, or visit harborhouse.com to view "
                    "their order history. Thank them for calling Harbor House."
                )
            )
            return

        self.order = order
        order_id = order.get("id")
        status_id = order.get("status_id", -1)
        status_label = STATUS_MAP.get(status_id, order.get("status", "Unknown"))

        if status_id not in CANCELLABLE_STATUS_IDS:
            # Order has already shipped, been completed, or is otherwise unmodifiable
            logging.info(
                "Order %s cannot be cancelled — current status: %s (%s)",
                order_id, status_label, status_id,
            )
            self.hangup(
                final_instructions=(
                    f"Let the customer know that unfortunately order #{order_id} cannot be "
                    f"cancelled because it is currently in '{status_label}' status — meaning "
                    "it has already progressed past the point where cancellation is possible. "
                    "Let them know they are welcome to initiate a return once the order has been "
                    "received. Direct them to harborhouse.com/returns or let them know the support "
                    "team can help them start a return. Apologize for any inconvenience and thank "
                    "them for calling Harbor House."
                )
            )
            return

        # Order is eligible — confirm the customer wants to proceed
        self.set_task(
            objective=(
                f"Order #{order_id} is eligible for cancellation. "
                "Confirm with the customer that they want to proceed."
            ),
            checklist=[
                guava.Say(
                    f"I found your order #{order_id}. It's currently in '{status_label}' status, "
                    "so we can cancel it. Just to confirm — would you like to go ahead and cancel this order?"
                ),
                guava.Field(
                    key="confirm_cancel",
                    description=(
                        "Ask the customer to confirm whether they want to cancel the order. "
                        "Capture 'yes, cancel it' or 'no, keep my order'."
                    ),
                    field_type="multiple_choice",
                    choices=["yes, cancel it", "no, keep my order"],
                    required=True,
                ),
            ],
            on_complete=self.process_cancellation,
        )

    def process_cancellation(self):
        confirm = self.get_field("confirm_cancel")
        cancel_reason = self.get_field("cancel_reason")
        order_id = self.order.get("id")

        if not confirm or "yes" not in confirm.lower():
            self.hangup(
                final_instructions=(
                    f"Let the customer know their order #{order_id} has not been cancelled "
                    "and will continue to be processed as normal. Thank them for calling "
                    "Harbor House and wish them a great day."
                )
            )
            return

        # Apply the cancellation to BigCommerce
        # status_id 5 = Cancelled; include the reason in staff_notes for the ops team
        staff_note = f"Cancelled via phone — reason: {cancel_reason}. Timestamp: {datetime.now(timezone.utc).isoformat()}Z"
        try:
            update_resp = requests.put(
                f"{V2_BASE}/orders/{order_id}",
                headers=HEADERS,
                json={"status_id": 5, "staff_notes": staff_note},
                timeout=10,
            )
            update_resp.raise_for_status()
            logging.info("Order %s successfully cancelled in BigCommerce.", order_id)
        except Exception as e:
            logging.error("Failed to cancel order %s in BigCommerce: %s", order_id, e)
            self.hangup(
                final_instructions=(
                    "Apologize to the customer and let them know there was a technical issue "
                    "processing the cancellation. Ask them to call back or visit harborhouse.com "
                    "to cancel through their account. Thank them for their patience."
                )
            )
            return

        print(json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "order_id": order_id,
            "action": "cancelled",
            "cancel_reason": cancel_reason,
            "staff_note": staff_note,
        }, indent=2))

        self.hangup(
            final_instructions=(
                f"Confirm to the customer that order #{order_id} has been successfully cancelled. "
                "Let them know they will receive a cancellation confirmation email shortly. "
                "If a payment was already processed, let them know any applicable refund will be "
                "returned to their original payment method within 5 to 7 business days. "
                "Thank them for calling Harbor House and wish them a great day."
            )
        )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=OrderCancellationController,
    )

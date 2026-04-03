import guava
import os
import logging
import argparse
import requests

logging.basicConfig(level=logging.INFO)

STORE_HASH = os.environ["BIGCOMMERCE_STORE_HASH"]
ACCESS_TOKEN = os.environ["BIGCOMMERCE_ACCESS_TOKEN"]
BASE_V2 = f"https://api.bigcommerce.com/stores/{STORE_HASH}/v2"

HEADERS = {
    "X-Auth-Token": ACCESS_TOKEN,
    "Content-Type": "application/json",
    "Accept": "application/json",
}

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

# Map issue type to a human-readable description and available resolutions
ISSUE_DESCRIPTIONS = {
    "backorder": "one or more items in your order are on backorder and not yet available to ship",
    "missing_item": "our fulfillment team flagged that an item may be missing from your shipment",
    "payment_issue": "there was a problem processing the payment for your order",
}

ISSUE_CHOICES = {
    "backorder": ["wait for backorder", "cancel and refund", "ship available items now"],
    "missing_item": ["send the missing item", "receive a partial refund", "return everything for a full refund"],
    "payment_issue": ["update payment method", "cancel order"],
}

# Map caller's choice to the BigCommerce order status to apply
CHOICE_STATUS_MAP = {
    "wait for backorder": 11,         # Awaiting Fulfillment
    "cancel and refund": 5,           # Cancelled
    "ship available items now": 3,    # Partially Shipped
    "send the missing item": 9,       # Awaiting Shipment
    "receive a partial refund": 3,    # Partially Shipped
    "return everything for a full refund": 4,  # Refunded
    "update payment method": 7,       # Awaiting Payment
    "cancel order": 5,                # Cancelled
}


def fetch_order(order_id: int) -> dict:
    resp = requests.get(
        f"{BASE_V2}/orders/{order_id}",
        headers=HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def update_order_status(order_id: int, status_id: int) -> dict:
    resp = requests.put(
        f"{BASE_V2}/orders/{order_id}",
        headers=HEADERS,
        json={"status_id": status_id},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


class OrderIssueFollowupController(guava.CallController):
    def __init__(self, customer_name: str, order_id: int, issue_type: str):
        super().__init__()
        self.customer_name = customer_name
        self.order_id = order_id
        self.issue_type = issue_type

        self.order = None
        try:
            self.order = fetch_order(order_id)
        except Exception as e:
            logging.error("Pre-fetch failed for order %s: %s", order_id, e)

        self.issue_description = ISSUE_DESCRIPTIONS.get(
            issue_type, "there is an issue with your order that needs your attention"
        )
        self.choices = ISSUE_CHOICES.get(issue_type, ["speak with support"])

        self.set_persona(
            organization_name="Crestline Outdoor Gear",
            agent_name="Sierra",
            agent_purpose="to proactively reach customers about issues with their orders and resolve them",
        )

        self.reach_person(
            contact_full_name=self.customer_name,
            on_success=self.begin_call,
            on_failure=self.recipient_unavailable,
        )

    def begin_call(self):
        self.set_task(
            objective=(
                f"Inform {self.customer_name} about the issue with order #{self.order_id}, "
                f"explain the situation clearly, offer the available resolution options, "
                "and update the order status based on their choice."
            ),
            checklist=[
                guava.Say(
                    f"Hi, may I please speak with {self.customer_name}? "
                    f"This is Sierra calling from Crestline Outdoor Gear regarding order #{self.order_id}."
                ),
                guava.Say(
                    f"I'm reaching out because {self.issue_description}. "
                    "I'd like to help you resolve this as quickly as possible."
                ),
                guava.Field(
                    key="resolution",
                    field_type="multiple_choice",
                    description=(
                        f"Explain each option clearly and ask {self.customer_name} how they'd like to proceed."
                    ),
                    choices=self.choices,
                    required=True,
                ),
            ],
            on_complete=self.handle_outcome,
        )

    def handle_outcome(self):
        resolution = self.get_field("resolution")
        new_status_id = CHOICE_STATUS_MAP.get(resolution)
        update_succeeded = False

        if new_status_id is not None:
            try:
                update_order_status(self.order_id, new_status_id)
                update_succeeded = True
                logging.info(
                    "Order %s updated to status %s (%s) based on resolution '%s'.",
                    self.order_id, new_status_id, ORDER_STATUSES.get(new_status_id), resolution,
                )
            except Exception as e:
                logging.error("Failed to update order %s: %s", self.order_id, e)

        if update_succeeded:
            self.hangup(
                final_instructions=(
                    f"Thank {self.customer_name} for their time and confirm that their choice "
                    f"of '{resolution}' has been applied to order #{self.order_id}. "
                    "Tell them they will receive a confirmation email shortly. "
                    "Be warm and professional."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    f"Apologize to {self.customer_name} and let them know their preference of "
                    f"'{resolution}' was noted but there was a system error applying it automatically. "
                    "Assure them a support agent will follow up within one business day. "
                    "Thank them for their patience."
                )
            )

    def recipient_unavailable(self):
        self.hangup(
            final_instructions=(
                f"Leave a concise voicemail for {self.customer_name}. "
                f"Mention you are Sierra from Crestline Outdoor Gear calling about order #{self.order_id}. "
                f"Explain that {self.issue_description} and that you'd like to help resolve it. "
                "Provide a callback number (use 1-800-555-0192) and ask them to call back at their earliest convenience."
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Outbound call to follow up with a customer about a flagged order issue."
    )
    parser.add_argument("phone", help="Customer phone number in E.164 format (e.g. +12125550101)")
    parser.add_argument("--order-id", required=True, type=int, help="BigCommerce order ID")
    parser.add_argument("--name", required=True, help="Customer's full name")
    parser.add_argument(
        "--issue",
        required=True,
        choices=list(ISSUE_DESCRIPTIONS.keys()),
        help="Issue type: backorder | missing_item | payment_issue",
    )
    args = parser.parse_args()

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=OrderIssueFollowupController(
            customer_name=args.name,
            order_id=args.order_id,
            issue_type=args.issue,
        ),
    )

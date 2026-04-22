import guava
import os
import logging
from guava import logging_utils
import argparse
import requests


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


agent = guava.Agent(
    name="Sierra",
    organization="Crestline Outdoor Gear",
    purpose="to proactively reach customers about issues with their orders and resolve them",
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    order_id = int(call.get_variable("order_id"))
    issue_type = call.get_variable("issue_type")

    order = None
    try:
        order = fetch_order(order_id)
    except Exception as e:
        logging.error("Pre-fetch failed for order %s: %s", order_id, e)

    issue_description = ISSUE_DESCRIPTIONS.get(
        issue_type, "there is an issue with your order that needs your attention"
    )
    choices = ISSUE_CHOICES.get(issue_type, ["speak with support"])

    call.data = {
        "order": order,
        "issue_description": issue_description,
        "choices": choices,
    }

    call.reach_person(contact_full_name=customer_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    if outcome == "unavailable":
        customer_name = call.get_variable("customer_name")
        order_id = call.get_variable("order_id")
        issue_description = call.data.get("issue_description", "there is an issue with your order")
        call.hangup(
            final_instructions=(
                f"Leave a concise voicemail for {customer_name}. "
                f"Mention you are Sierra from Crestline Outdoor Gear calling about order #{order_id}. "
                f"Explain that {issue_description} and that you'd like to help resolve it. "
                "Provide a callback number (use 1-800-555-0192) and ask them to call back at their earliest convenience."
            )
        )
    elif outcome == "available":
        customer_name = call.get_variable("customer_name")
        order_id = call.get_variable("order_id")
        issue_description = call.data.get("issue_description", "there is an issue with your order")
        choices = call.data.get("choices", ["speak with support"])

        call.set_task(
            "order_issue_resolution",
            objective=(
                f"Inform {customer_name} about the issue with order #{order_id}, "
                f"explain the situation clearly, offer the available resolution options, "
                "and update the order status based on their choice."
            ),
            checklist=[
                guava.Say(
                    f"Hi, may I please speak with {customer_name}? "
                    f"This is Sierra calling from Crestline Outdoor Gear regarding order #{order_id}."
                ),
                guava.Say(
                    f"I'm reaching out because {issue_description}. "
                    "I'd like to help you resolve this as quickly as possible."
                ),
                guava.Field(
                    key="resolution",
                    field_type="multiple_choice",
                    description=(
                        f"Explain each option clearly and ask {customer_name} how they'd like to proceed."
                    ),
                    choices=choices,
                    required=True,
                ),
            ],
        )


@agent.on_task_complete("order_issue_resolution")
def on_done(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    order_id = int(call.get_variable("order_id"))

    resolution = call.get_field("resolution")
    new_status_id = CHOICE_STATUS_MAP.get(resolution)
    update_succeeded = False

    if new_status_id is not None:
        try:
            update_order_status(order_id, new_status_id)
            update_succeeded = True
            logging.info(
                "Order %s updated to status %s (%s) based on resolution '%s'.",
                order_id, new_status_id, ORDER_STATUSES.get(new_status_id), resolution,
            )
        except Exception as e:
            logging.error("Failed to update order %s: %s", order_id, e)

    if update_succeeded:
        call.hangup(
            final_instructions=(
                f"Thank {customer_name} for their time and confirm that their choice "
                f"of '{resolution}' has been applied to order #{order_id}. "
                "Tell them they will receive a confirmation email shortly. "
                "Be warm and professional."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Apologize to {customer_name} and let them know their preference of "
                f"'{resolution}' was noted but there was a system error applying it automatically. "
                "Assure them a support agent will follow up within one business day. "
                "Thank them for their patience."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
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

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "customer_name": args.name,
            "order_id": str(args.order_id),
            "issue_type": args.issue,
        },
    )

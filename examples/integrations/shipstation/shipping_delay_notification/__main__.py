import guava
import os
import logging
from guava import logging_utils
import argparse
import requests
import base64


API_KEY = os.environ["SHIPSTATION_API_KEY"]
API_SECRET = os.environ["SHIPSTATION_API_SECRET"]
BASE_URL = "https://ssapi.shipstation.com"

credentials = base64.b64encode(f"{API_KEY}:{API_SECRET}".encode()).decode()
HEADERS = {
    "Authorization": f"Basic {credentials}",
    "Content-Type": "application/json",
}


def fetch_order(order_number: str) -> dict | None:
    resp = requests.get(
        f"{BASE_URL}/orders",
        headers=HEADERS,
        params={"orderNumber": order_number, "sortBy": "OrderDate", "sortDir": "DESC", "pageSize": "1"},
        timeout=10,
    )
    resp.raise_for_status()
    orders = resp.json().get("orders", [])
    return orders[0] if orders else None


def cancel_order(order_id: int) -> None:
    resp = requests.delete(
        f"{BASE_URL}/orders/{order_id}",
        headers=HEADERS,
        timeout=10,
    )
    resp.raise_for_status()


def hold_order(order_id: int) -> None:
    resp = requests.put(
        f"{BASE_URL}/orders/holdorder",
        headers=HEADERS,
        json={"orderId": order_id},
        timeout=10,
    )
    resp.raise_for_status()


def add_order_note(order_id: int, existing_notes: str, note: str) -> None:
    combined = f"{existing_notes}\n{note}".strip() if existing_notes else note
    resp = requests.post(
        f"{BASE_URL}/orders/createorder",
        headers=HEADERS,
        json={"orderId": order_id, "internalNotes": combined},
        timeout=10,
    )
    resp.raise_for_status()


agent = guava.Agent(
    name="Morgan",
    organization="Pacific Home Goods",
    purpose="to keep customers informed about their orders and help resolve shipping delays",
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    order_number = call.get_variable("order_number")

    try:
        call.set_variable("order", fetch_order(order_number))
    except Exception as e:
        logging.error("Pre-fetch order failed: %s", e)
        call.set_variable("order", None)

    call.reach_person(contact_full_name=customer_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    customer_name = call.get_variable("customer_name")
    order_number = call.get_variable("order_number")
    updated_delivery_date = call.get_variable("updated_delivery_date")

    if outcome == "unavailable":
        call.hangup(
            final_instructions=(
                f"Leave a concise voicemail for {customer_name}. "
                f"Mention you are calling from Pacific Home Goods about order #{order_number}. "
                f"Let them know there is a shipping delay and the new estimated delivery "
                f"is {updated_delivery_date}. "
                "Ask them to call 1-800-555-0214 or visit pacifichomegoods.com/orders "
                "if they have questions or want to make changes. Keep it under 30 seconds."
            )
        )
    elif outcome == "available":
        delay_reason = call.get_variable("delay_reason")
        original_delivery_date = call.get_variable("original_delivery_date")
        call.set_task(
            "handle_outcome",
            objective=(
                f"Inform {customer_name} that their order #{order_number} is delayed, "
                "explain the reason, provide an updated estimated delivery date, "
                "and offer resolution options."
            ),
            checklist=[
                guava.Say(
                    f"Hi, is this {customer_name}? "
                    "This is Morgan calling from Pacific Home Goods. "
                    "I'm reaching out with an update about your order — do you have just a moment?"
                ),
                guava.Say(
                    f"I'm sorry to let you know that order #{order_number} is experiencing "
                    f"a shipping delay due to {delay_reason}. "
                    f"Your original estimated delivery was {original_delivery_date}, "
                    f"and the updated estimate is now {updated_delivery_date}. "
                    "We sincerely apologize for the inconvenience."
                ),
                guava.Field(
                    key="customer_option",
                    field_type="multiple_choice",
                    description=(
                        "Ask the customer how they would like to proceed given the delay. "
                        "Offer three options: wait for the updated delivery date, "
                        "cancel the order for a full refund, or expedite shipping at no extra charge."
                    ),
                    choices=["wait for updated delivery", "cancel for refund", "expedite shipping"],
                    required=True,
                ),
                guava.Field(
                    key="additional_concerns",
                    field_type="text",
                    description="Ask if there is anything else the customer would like to share or any questions they have.",
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("handle_outcome")
def on_done(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    order_number = call.get_variable("order_number")
    delay_reason = call.get_variable("delay_reason")
    original_delivery_date = call.get_variable("original_delivery_date")
    updated_delivery_date = call.get_variable("updated_delivery_date")

    customer_option = call.get_field("customer_option")
    additional_concerns = call.get_field("additional_concerns") or "None"

    order = call.get_variable("order")
    order_id = order.get("orderId") if order else None
    existing_notes = (order.get("internalNotes", "") or "") if order else ""

    note = (
        f"[DELAY NOTIFICATION] Reason: {delay_reason}. "
        f"Original delivery: {original_delivery_date}. "
        f"Updated delivery: {updated_delivery_date}. "
        f"Customer choice: {customer_option}. "
        f"Additional concerns: {additional_concerns}."
    )

    if order_id:
        if customer_option == "cancel for refund":
            try:
                cancel_order(order_id)
                logging.info("Cancelled order %s per customer request", order_number)
            except Exception as e:
                logging.error("Failed to cancel order %s: %s", order_number, e)
        elif customer_option == "expedite shipping":
            try:
                # Place on hold so the fulfillment team can upgrade the service
                hold_order(order_id)
                logging.info("Placed order %s on hold for expedite processing", order_number)
            except Exception as e:
                logging.error("Failed to hold order %s: %s", order_number, e)

        try:
            add_order_note(order_id, existing_notes, note)
            logging.info("Updated internal notes on order %s", order_number)
        except Exception as e:
            logging.error("Failed to update order notes: %s", e)

    if customer_option == "cancel for refund":
        call.hangup(
            final_instructions=(
                f"Thank {customer_name} for their understanding. "
                f"Confirm that order #{order_number} has been cancelled and a full refund "
                "will be issued to their original payment method within 3-5 business days. "
                "Apologize again for the delay and invite them to shop with Pacific Home Goods again. "
                "Offer the support line (1-800-555-0214) for any follow-up questions."
            )
        )
    elif customer_option == "expedite shipping":
        call.hangup(
            final_instructions=(
                f"Thank {customer_name} for their patience. "
                f"Confirm that order #{order_number} has been flagged for expedited shipping "
                "at no additional cost to them. "
                f"Let them know they can expect delivery by {updated_delivery_date} or sooner, "
                "and they'll receive a new tracking email once the label is updated. "
                "Apologize again for the inconvenience."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {customer_name} for their patience. "
                f"Confirm that order #{order_number} is on its way and the updated "
                f"estimated delivery date is {updated_delivery_date}. "
                "Let them know they'll receive a tracking update via email. "
                "Apologize once more for the delay and thank them for choosing Pacific Home Goods."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Proactively call a customer about a shipping delay on their order."
    )
    parser.add_argument("phone", help="Customer phone number in E.164 format (e.g. +15551234567)")
    parser.add_argument("--order-number", required=True, help="ShipStation order number")
    parser.add_argument("--name", required=True, help="Customer full name")
    parser.add_argument(
        "--delay-reason",
        required=True,
        help='Reason for the delay (e.g. "severe weather affecting the carrier network")',
    )
    parser.add_argument(
        "--original-delivery-date",
        required=True,
        help="Original estimated delivery date (e.g. March 28)",
    )
    parser.add_argument(
        "--updated-delivery-date",
        required=True,
        help="Updated estimated delivery date (e.g. April 2)",
    )
    args = parser.parse_args()

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "customer_name": args.name,
            "order_number": args.order_number,
            "delay_reason": args.delay_reason,
            "original_delivery_date": args.original_delivery_date,
            "updated_delivery_date": args.updated_delivery_date,
        },
    )

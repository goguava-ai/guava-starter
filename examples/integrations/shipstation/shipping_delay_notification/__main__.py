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


class ShippingDelayController(guava.CallController):
    def __init__(
        self,
        customer_name: str,
        order_number: str,
        delay_reason: str,
        original_delivery_date: str,
        updated_delivery_date: str,
    ):
        super().__init__()
        self.customer_name = customer_name
        self.order_number = order_number
        self.delay_reason = delay_reason
        self.original_delivery_date = original_delivery_date
        self.updated_delivery_date = updated_delivery_date

        try:
            self.order = fetch_order(order_number)
        except Exception as e:
            logging.error("Pre-fetch order failed: %s", e)
            self.order = None

        self.set_persona(
            organization_name="Pacific Home Goods",
            agent_name="Morgan",
            agent_purpose="to keep customers informed about their orders and help resolve shipping delays",
        )

        self.reach_person(
            contact_full_name=self.customer_name,
            on_success=self.begin_call,
            on_failure=self.recipient_unavailable,
        )

    def begin_call(self):
        self.set_task(
            objective=(
                f"Inform {self.customer_name} that their order #{self.order_number} is delayed, "
                "explain the reason, provide an updated estimated delivery date, "
                "and offer resolution options."
            ),
            checklist=[
                guava.Say(
                    f"Hi, is this {self.customer_name}? "
                    "This is Morgan calling from Pacific Home Goods. "
                    "I'm reaching out with an update about your order — do you have just a moment?"
                ),
                guava.Say(
                    f"I'm sorry to let you know that order #{self.order_number} is experiencing "
                    f"a shipping delay due to {self.delay_reason}. "
                    f"Your original estimated delivery was {self.original_delivery_date}, "
                    f"and the updated estimate is now {self.updated_delivery_date}. "
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
            on_complete=self.handle_outcome,
        )

    def handle_outcome(self):
        customer_option = self.get_field("customer_option")
        additional_concerns = self.get_field("additional_concerns") or "None"

        order_id = self.order.get("orderId") if self.order else None
        existing_notes = (self.order.get("internalNotes", "") or "") if self.order else ""

        note = (
            f"[DELAY NOTIFICATION] Reason: {self.delay_reason}. "
            f"Original delivery: {self.original_delivery_date}. "
            f"Updated delivery: {self.updated_delivery_date}. "
            f"Customer choice: {customer_option}. "
            f"Additional concerns: {additional_concerns}."
        )

        if order_id:
            if customer_option == "cancel for refund":
                try:
                    cancel_order(order_id)
                    logging.info("Cancelled order %s per customer request", self.order_number)
                except Exception as e:
                    logging.error("Failed to cancel order %s: %s", self.order_number, e)
            elif customer_option == "expedite shipping":
                try:
                    # Place on hold so the fulfillment team can upgrade the service
                    hold_order(order_id)
                    logging.info("Placed order %s on hold for expedite processing", self.order_number)
                except Exception as e:
                    logging.error("Failed to hold order %s: %s", self.order_number, e)

            try:
                add_order_note(order_id, existing_notes, note)
                logging.info("Updated internal notes on order %s", self.order_number)
            except Exception as e:
                logging.error("Failed to update order notes: %s", e)

        if customer_option == "cancel for refund":
            self.hangup(
                final_instructions=(
                    f"Thank {self.customer_name} for their understanding. "
                    f"Confirm that order #{self.order_number} has been cancelled and a full refund "
                    "will be issued to their original payment method within 3-5 business days. "
                    "Apologize again for the delay and invite them to shop with Pacific Home Goods again. "
                    "Offer the support line (1-800-555-0214) for any follow-up questions."
                )
            )
        elif customer_option == "expedite shipping":
            self.hangup(
                final_instructions=(
                    f"Thank {self.customer_name} for their patience. "
                    f"Confirm that order #{self.order_number} has been flagged for expedited shipping "
                    "at no additional cost to them. "
                    f"Let them know they can expect delivery by {self.updated_delivery_date} or sooner, "
                    "and they'll receive a new tracking email once the label is updated. "
                    "Apologize again for the inconvenience."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    f"Thank {self.customer_name} for their patience. "
                    f"Confirm that order #{self.order_number} is on its way and the updated "
                    f"estimated delivery date is {self.updated_delivery_date}. "
                    "Let them know they'll receive a tracking update via email. "
                    "Apologize once more for the delay and thank them for choosing Pacific Home Goods."
                )
            )

    def recipient_unavailable(self):
        self.hangup(
            final_instructions=(
                f"Leave a concise voicemail for {self.customer_name}. "
                f"Mention you are calling from Pacific Home Goods about order #{self.order_number}. "
                f"Let them know there is a shipping delay and the new estimated delivery "
                f"is {self.updated_delivery_date}. "
                "Ask them to call 1-800-555-0214 or visit pacifichomegoods.com/orders "
                "if they have questions or want to make changes. Keep it under 30 seconds."
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

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=ShippingDelayController(
            customer_name=args.name,
            order_number=args.order_number,
            delay_reason=args.delay_reason,
            original_delivery_date=args.original_delivery_date,
            updated_delivery_date=args.updated_delivery_date,
        ),
    )

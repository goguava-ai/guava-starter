import guava
import os
import logging
import json
import argparse
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)


class OrderStatusController(guava.CallController):
    def __init__(self, contact_name, order_number, original_date, new_date):
        super().__init__()
        self.contact_name = contact_name
        self.order_number = order_number
        self.original_date = original_date
        self.new_date = new_date
        self.set_persona(
            organization_name="ShopNow",
            agent_name="Alex",
            agent_purpose=(
                "to inform customers about shipment delays, confirm new delivery windows, "
                "and help resolve any issues related to their delayed order"
            ),
        )
        self.reach_person(
            contact_full_name=self.contact_name,
            on_success=self.begin_delay_notification,
            on_failure=self.recipient_unavailable,
        )

    def begin_delay_notification(self):
        self.set_task(
            objective=(
                f"Notify {self.contact_name} that their ShopNow order #{self.order_number} "
                f"has been delayed from the original delivery date of {self.original_date} "
                f"to a new estimated delivery date of {self.new_date}. "
                "Apologize for the inconvenience, confirm the customer has understood the delay, "
                "and determine their preferred resolution: wait for the revised delivery, "
                "have the order reshipped, or receive a full refund. "
                "If they choose reship, collect an updated delivery address if needed. "
                "Invite them to share any additional concerns before ending the call."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.contact_name}, this is Alex calling from ShopNow. "
                    f"I'm reaching out about your order number {self.order_number}. "
                    f"Unfortunately, your shipment has been delayed. "
                    f"Your original delivery date was {self.original_date}, "
                    f"and the new estimated delivery date is {self.new_date}. "
                    "We sincerely apologize for any inconvenience this may cause."
                ),
                guava.Field(
                    key="delay_acknowledged",
                    description="Confirm that the customer has acknowledged and understood the shipment delay",
                    field_type="text",
                    required=True,
                ),
                guava.Say(
                    "We want to make this right for you. You have a few options: "
                    "you can wait for the revised delivery date, we can reship your order, "
                    "or we can process a full refund for you."
                ),
                guava.Field(
                    key="resolution_preference",
                    description=(
                        "The customer's preferred resolution for the delay: "
                        "'wait' to wait for the new delivery date, "
                        "'reship' to have the order reshipped, "
                        "or 'refund' for a full refund"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="new_delivery_address",
                    description=(
                        "If the customer chose reship, capture their preferred delivery address. "
                        "Leave blank if they want to use the original address or chose another resolution."
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="additional_concerns",
                    description="Any additional concerns or questions the customer raised during the call",
                    field_type="text",
                    required=False,
                ),
            ],
            on_complete=self.save_results,
        )

    def save_results(self):
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "contact_name": self.contact_name,
            "order_number": self.order_number,
            "original_delivery_date": self.original_date,
            "new_estimated_delivery_date": self.new_date,
            "delay_acknowledged": self.get_field("delay_acknowledged"),
            "resolution_preference": self.get_field("resolution_preference"),
            "new_delivery_address": self.get_field("new_delivery_address"),
            "additional_concerns": self.get_field("additional_concerns"),
        }
        print(json.dumps(results, indent=2))
        logging.info("Order status call completed for order %s", self.order_number)
        self.hangup(
            final_instructions=(
                "Thank the customer for their patience and understanding. "
                "Confirm the next steps based on their chosen resolution and let them know "
                "ShopNow's support team is available if they have further questions. "
                "Wish them a great day and end the call politely."
            )
        )

    def recipient_unavailable(self):
        logging.warning(
            "Could not reach %s for order status notification on order %s.",
            self.contact_name,
            self.order_number,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ShopNow order delay notification agent")
    parser.add_argument("phone", help="Customer phone number to call")
    parser.add_argument("--name", required=True, help="Customer full name")
    parser.add_argument("--order-number", required=True, help="Order number")
    parser.add_argument("--original-date", required=True, help="Original estimated delivery date")
    parser.add_argument("--new-date", required=True, help="New estimated delivery date")
    args = parser.parse_args()

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=OrderStatusController(
            contact_name=args.name,
            order_number=args.order_number,
            original_date=args.original_date,
            new_date=args.new_date,
        ),
    )

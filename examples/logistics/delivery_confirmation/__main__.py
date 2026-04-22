import guava
import os
import logging
import json
import argparse
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)


class DeliveryConfirmationController(guava.CallController):
    def __init__(self, recipient_name, tracking_number, delivery_date, delivery_window):
        super().__init__()
        self.recipient_name = recipient_name
        self.tracking_number = tracking_number
        self.delivery_date = delivery_date
        self.delivery_window = delivery_window

        self.set_persona(
            organization_name="SwiftShip Logistics",
            agent_name="Jordan",
            agent_purpose=(
                f"confirm an upcoming delivery for tracking number {self.tracking_number} "
                f"scheduled for {self.delivery_date} {self.delivery_window}, "
                "collect any access instructions, and record verbal confirmation"
            ),
        )

        self.reach_person(
            contact_full_name=self.recipient_name,
            on_success=self.start_confirmation,
            on_failure=self.recipient_unavailable,
        )

    def start_confirmation(self):
        self.set_task(
            objective=(
                f"Confirm the upcoming delivery for tracking number {self.tracking_number} "
                f"scheduled for {self.delivery_date} {self.delivery_window}. "
                "Collect any special access instructions, a safe drop location if the recipient "
                "won't be available, an alternative contact if needed, and acknowledge whether "
                "a signature will be required."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.recipient_name}, I'm calling from SwiftShip Logistics regarding "
                    f"your upcoming delivery. Your tracking number is {self.tracking_number} and "
                    f"it is scheduled for {self.delivery_date} {self.delivery_window}."
                ),
                guava.Field(
                    key="delivery_confirmed",
                    description="Whether the recipient confirms they are expecting the delivery and the date/window works for them",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="access_instructions",
                    description="Any special access instructions for the delivery location, such as gate codes, building entry steps, or parking notes",
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="safe_drop_location",
                    description="A safe location to leave the package if the recipient is unavailable at time of delivery",
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="alternative_contact",
                    description="An alternative contact person or phone number in case the recipient cannot be reached on delivery day",
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="signature_required_acknowledged",
                    description="Whether the recipient acknowledges that a signature will be required upon delivery",
                    field_type="text",
                    required=True,
                ),
            ],
            on_complete=self.save_results,
        )

    def save_results(self):
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tracking_number": self.tracking_number,
            "recipient_name": self.recipient_name,
            "delivery_date": self.delivery_date,
            "delivery_window": self.delivery_window,
            "delivery_confirmed": self.get_field("delivery_confirmed"),
            "access_instructions": self.get_field("access_instructions"),
            "safe_drop_location": self.get_field("safe_drop_location"),
            "alternative_contact": self.get_field("alternative_contact"),
            "signature_required_acknowledged": self.get_field("signature_required_acknowledged"),
        }
        print(json.dumps(results, indent=2))
        logging.info("Delivery confirmation results saved.")
        self.hangup(
            final_instructions=(
                "Thank the recipient for confirming their delivery. Let them know that SwiftShip "
                "Logistics will be in touch if there are any changes to the delivery window, and "
                "wish them a great day."
            )
        )

    def recipient_unavailable(self):
        logging.warning(
            f"Could not reach {self.recipient_name} for delivery confirmation on tracking number {self.tracking_number}."
        )
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tracking_number": self.tracking_number,
            "recipient_name": self.recipient_name,
            "delivery_date": self.delivery_date,
            "delivery_window": self.delivery_window,
            "status": "recipient_unavailable",
        }
        print(json.dumps(results, indent=2))
        self.hangup(
            final_instructions=(
                "Leave a polite voicemail letting the recipient know that SwiftShip Logistics "
                f"called regarding tracking number {self.tracking_number} scheduled for "
                f"{self.delivery_date} {self.delivery_window}, and ask them to call back or "
                "visit the SwiftShip website to update their delivery preferences."
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SwiftShip Logistics - Delivery Confirmation Agent")
    parser.add_argument("phone", help="Recipient phone number to call")
    parser.add_argument("--name", required=True, help="Full name of the recipient")
    parser.add_argument("--tracking-number", required=True, help="Shipment tracking number")
    parser.add_argument("--delivery-date", required=True, help="Scheduled delivery date (e.g. March 1st)")
    parser.add_argument(
        "--delivery-window",
        required=True,
        help="Delivery time window (e.g. 'between 10am and 2pm')",
    )
    args = parser.parse_args()

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=DeliveryConfirmationController(
            recipient_name=args.name,
            tracking_number=args.tracking_number,
            delivery_date=args.delivery_date,
            delivery_window=args.delivery_window,
        ),
    )

import guava
import os
import logging
from guava import logging_utils
import json
import argparse
from datetime import datetime, timezone


agent = guava.Agent(
    name="Jordan",
    organization="SwiftShip Logistics",
    purpose=(
        "confirm an upcoming delivery, "
        "collect any access instructions, and record verbal confirmation"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(contact_full_name=call.get_variable("recipient_name"))


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    recipient_name = call.get_variable("recipient_name")
    tracking_number = call.get_variable("tracking_number")
    delivery_date = call.get_variable("delivery_date")
    delivery_window = call.get_variable("delivery_window")

    if outcome == "unavailable":
        logging.warning(
            f"Could not reach {recipient_name} for delivery confirmation on tracking number {tracking_number}."
        )
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tracking_number": tracking_number,
            "recipient_name": recipient_name,
            "delivery_date": delivery_date,
            "delivery_window": delivery_window,
            "status": "recipient_unavailable",
        }
        print(json.dumps(results, indent=2))
        call.hangup(
            final_instructions=(
                "Leave a polite voicemail letting the recipient know that SwiftShip Logistics "
                f"called regarding tracking number {tracking_number} scheduled for "
                f"{delivery_date} {delivery_window}, and ask them to call back or "
                "visit the SwiftShip website to update their delivery preferences."
            )
        )
    elif outcome == "available":
        call.set_task(
            "delivery_confirmation",
            objective=(
                f"Confirm the upcoming delivery for tracking number {tracking_number} "
                f"scheduled for {delivery_date} {delivery_window}. "
                "Collect any special access instructions, a safe drop location if the recipient "
                "won't be available, an alternative contact if needed, and acknowledge whether "
                "a signature will be required."
            ),
            checklist=[
                guava.Say(
                    f"Hi {recipient_name}, I'm calling from SwiftShip Logistics regarding "
                    f"your upcoming delivery. Your tracking number is {tracking_number} and "
                    f"it is scheduled for {delivery_date} {delivery_window}."
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
        )


@agent.on_task_complete("delivery_confirmation")
def on_done(call: guava.Call) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tracking_number": call.get_variable("tracking_number"),
        "recipient_name": call.get_variable("recipient_name"),
        "delivery_date": call.get_variable("delivery_date"),
        "delivery_window": call.get_variable("delivery_window"),
        "delivery_confirmed": call.get_field("delivery_confirmed"),
        "access_instructions": call.get_field("access_instructions"),
        "safe_drop_location": call.get_field("safe_drop_location"),
        "alternative_contact": call.get_field("alternative_contact"),
        "signature_required_acknowledged": call.get_field("signature_required_acknowledged"),
    }
    print(json.dumps(results, indent=2))
    logging.info("Delivery confirmation results saved.")
    call.hangup(
        final_instructions=(
            "Thank the recipient for confirming their delivery. Let them know that SwiftShip "
            "Logistics will be in touch if there are any changes to the delivery window, and "
            "wish them a great day."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
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

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "recipient_name": args.name,
            "tracking_number": args.tracking_number,
            "delivery_date": args.delivery_date,
            "delivery_window": args.delivery_window,
        },
    )

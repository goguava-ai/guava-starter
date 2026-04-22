import argparse
import json
import logging
import os
from datetime import datetime, timezone

import guava
from guava import logging_utils

agent = guava.Agent(
    name="Alex",
    organization="ShopNow",
    purpose=(
        "to inform customers about shipment delays, confirm new delivery windows, "
        "and help resolve any issues related to their delayed order"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(contact_full_name=call.get_variable("contact_name"))


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    contact_name = call.get_variable("contact_name")
    order_number = call.get_variable("order_number")
    original_date = call.get_variable("original_date")
    new_date = call.get_variable("new_date")

    if outcome == "unavailable":
        logging.warning(
            "Could not reach %s for order status notification on order %s.",
            contact_name,
            order_number,
        )
    elif outcome == "available":
        call.set_task(
            "order_delay_notification",
            objective=(
                f"Notify {contact_name} that their ShopNow order #{order_number} "
                f"has been delayed from the original delivery date of {original_date} "
                f"to a new estimated delivery date of {new_date}. "
                "Apologize for the inconvenience, confirm the customer has understood the delay, "
                "and determine their preferred resolution: wait for the revised delivery, "
                "have the order reshipped, or receive a full refund. "
                "If they choose reship, collect an updated delivery address if needed. "
                "Invite them to share any additional concerns before ending the call."
            ),
            checklist=[
                guava.Say(
                    f"Hi {contact_name}, this is Alex calling from ShopNow. "
                    f"I'm reaching out about your order number {order_number}. "
                    f"Unfortunately, your shipment has been delayed. "
                    f"Your original delivery date was {original_date}, "
                    f"and the new estimated delivery date is {new_date}. "
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
        )


@agent.on_task_complete("order_delay_notification")
def on_done(call: guava.Call) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "contact_name": call.get_variable("contact_name"),
        "order_number": call.get_variable("order_number"),
        "original_delivery_date": call.get_variable("original_date"),
        "new_estimated_delivery_date": call.get_variable("new_date"),
        "delay_acknowledged": call.get_field("delay_acknowledged"),
        "resolution_preference": call.get_field("resolution_preference"),
        "new_delivery_address": call.get_field("new_delivery_address"),
        "additional_concerns": call.get_field("additional_concerns"),
    }
    print(json.dumps(results, indent=2))
    logging.info("Order status call completed for order %s", call.get_variable("order_number"))
    call.hangup(
        final_instructions=(
            "Thank the customer for their patience and understanding. "
            "Confirm the next steps based on their chosen resolution and let them know "
            "ShopNow's support team is available if they have further questions. "
            "Wish them a great day and end the call politely."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(description="ShopNow order delay notification agent")
    parser.add_argument("phone", help="Customer phone number to call")
    parser.add_argument("--name", required=True, help="Customer full name")
    parser.add_argument("--order-number", required=True, help="Order number")
    parser.add_argument("--original-date", required=True, help="Original estimated delivery date")
    parser.add_argument("--new-date", required=True, help="New estimated delivery date")
    args = parser.parse_args()

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "contact_name": args.name,
            "order_number": args.order_number,
            "original_date": args.original_date,
            "new_date": args.new_date,
        },
    )

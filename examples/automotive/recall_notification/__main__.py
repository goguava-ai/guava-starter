import guava
import os
import logging
from guava import logging_utils
import json
import argparse
from datetime import datetime


agent = guava.Agent(
    name="Morgan",
    organization="Lakeside Auto Group - Safety Team",
    purpose=(
        "notify vehicle owners about open safety recalls and collect their "
        "scheduling preferences so the required repair can be completed"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(contact_full_name=call.get_variable("customer_name"))


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    customer_name = call.get_variable("customer_name")
    vehicle = call.get_variable("vehicle")
    recall_number = call.get_variable("recall_number")
    recall_description = call.get_variable("recall_description")

    if outcome == "unavailable":
        logging.warning("Could not reach %s for recall notification call.", customer_name)
        results = {
            "timestamp": datetime.now().isoformat(),
            "customer_name": customer_name,
            "vehicle": vehicle,
            "recall_number": recall_number,
            "recall_description": recall_description,
            "status": "recipient_unavailable",
        }
        print(json.dumps(results, indent=2))
        call.hangup()
    elif outcome == "available":
        call.set_task(
            "recall_notification",
            objective=(
                f"Inform {customer_name} that their {vehicle} is affected by "
                f"safety recall {recall_number} ({recall_description}). "
                f"Confirm they are aware, verify they still have the vehicle, and collect "
                f"scheduling preferences so Lakeside Auto Group can complete the repair at "
                f"no charge."
            ),
            checklist=[
                guava.Say(
                    f"Notify {customer_name} that their {vehicle} has an open "
                    f"safety recall (Recall #{recall_number}) related to: "
                    f"{recall_description}. Emphasize the repair is free of charge."
                ),
                guava.Field(
                    key="recall_acknowledged",
                    description="Confirm the customer acknowledges they have been informed of the recall",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="vehicle_in_possession",
                    description="Whether the customer still owns or has access to the affected vehicle",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="appointment_date_preference",
                    description="The customer's preferred date to bring the vehicle in for the recall repair",
                    field_type="date",
                    required=True,
                ),
                guava.Field(
                    key="transportation_needed",
                    description="Whether the customer needs a loaner car, a shuttle, or neither during the repair",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="questions_about_recall",
                    description="Any questions or concerns the customer has about the recall or the repair process",
                    field_type="text",
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("recall_notification")
def on_recall_notification_done(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    results = {
        "timestamp": datetime.now().isoformat(),
        "customer_name": customer_name,
        "vehicle": call.get_variable("vehicle"),
        "recall_number": call.get_variable("recall_number"),
        "recall_description": call.get_variable("recall_description"),
        "recall_acknowledged": call.get_field("recall_acknowledged"),
        "vehicle_in_possession": call.get_field("vehicle_in_possession"),
        "appointment_date_preference": call.get_field("appointment_date_preference"),
        "transportation_needed": call.get_field("transportation_needed"),
        "questions_about_recall": call.get_field("questions_about_recall"),
    }

    print(json.dumps(results, indent=2))
    logging.info("Recall notification results collected for %s", customer_name)

    call.hangup(
        final_instructions=(
            f"Thank {customer_name} for their time. Reassure them that the recall "
            f"repair is straightforward and completely free. Confirm their appointment "
            f"preference has been noted and that someone from the service team will be "
            f"in touch with a confirmed time. Wish them a safe and pleasant day."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound recall notification call for Lakeside Auto Group Safety Team"
    )
    parser.add_argument("phone", help="Customer phone number to call")
    parser.add_argument("--name", required=True, help="Customer full name")
    parser.add_argument(
        "--vehicle",
        required=True,
        help='Vehicle year, make, and model (e.g. "2021 Toyota Camry")',
    )
    parser.add_argument("--recall-number", required=True, help="NHTSA or manufacturer recall number")
    parser.add_argument(
        "--recall-description",
        required=True,
        help="Brief description of the recall and affected component",
    )
    args = parser.parse_args()

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "customer_name": args.name,
            "vehicle": args.vehicle,
            "recall_number": args.recall_number,
            "recall_description": args.recall_description,
        },
    )

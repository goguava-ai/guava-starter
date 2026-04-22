import argparse
import json
import logging
import os
from datetime import datetime

import guava
from guava import logging_utils

agent = guava.Agent(
    name="Taylor",
    organization="Lakeside Auto Group",
    purpose=(
        "call customers who are due for routine maintenance and help them "
        "book a service bay appointment for their vehicle"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(contact_full_name=call.get_variable("customer_name"))


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    customer_name = call.get_variable("customer_name")
    vehicle = call.get_variable("vehicle")
    service_type = call.get_variable("service_type")
    mileage = call.get_variable("mileage")

    if outcome == "unavailable":
        logging.warning("Could not reach %s for service reminder call.", customer_name)
        results = {
            "timestamp": datetime.now().isoformat(),
            "customer_name": customer_name,
            "vehicle": vehicle,
            "service_type": service_type,
            "mileage": mileage,
            "status": "recipient_unavailable",
        }
        print(json.dumps(results, indent=2))
        call.hangup()
    elif outcome == "available":
        call.set_task(
            "service_reminder",
            objective=(
                f"Remind {customer_name} that their {vehicle} is due for "
                f"{service_type} at {mileage} miles, and schedule a "
                f"service bay appointment at Lakeside Auto Group."
            ),
            checklist=[
                guava.Say(
                    f"Let {customer_name} know their {vehicle} is due for "
                    f"{service_type} based on their current mileage of {mileage}."
                ),
                guava.Field(
                    key="service_acknowledged",
                    description="Confirm the customer acknowledges their vehicle is due for service",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="appointment_date_preference",
                    description="The customer's preferred date for their service appointment",
                    field_type="date",
                    required=True,
                ),
                guava.Field(
                    key="appointment_time_preference",
                    description="The customer's preferred time of day for the appointment (e.g. morning, afternoon, specific time)",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="loaner_car_needed",
                    description="Whether the customer will need a loaner car during the service",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="additional_service_requests",
                    description="Any additional services or concerns the customer would like addressed during the visit",
                    field_type="text",
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("service_reminder")
def on_service_reminder_done(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    results = {
        "timestamp": datetime.now().isoformat(),
        "customer_name": customer_name,
        "vehicle": call.get_variable("vehicle"),
        "service_type": call.get_variable("service_type"),
        "mileage": call.get_variable("mileage"),
        "service_acknowledged": call.get_field("service_acknowledged"),
        "appointment_date_preference": call.get_field("appointment_date_preference"),
        "appointment_time_preference": call.get_field("appointment_time_preference"),
        "loaner_car_needed": call.get_field("loaner_car_needed"),
        "additional_service_requests": call.get_field("additional_service_requests"),
    }

    print(json.dumps(results, indent=2))
    logging.info("Service reminder results collected for %s", customer_name)

    call.hangup(
        final_instructions=(
            f"Thank {customer_name} for their time, confirm their appointment "
            f"details, and let them know that Lakeside Auto Group will send a "
            f"confirmation. Wish them a great day."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound service reminder call for Lakeside Auto Group"
    )
    parser.add_argument("phone", help="Customer phone number to call")
    parser.add_argument("--name", required=True, help="Customer full name")
    parser.add_argument(
        "--vehicle",
        required=True,
        help='Vehicle year, make, and model (e.g. "2021 Toyota Camry")',
    )
    parser.add_argument(
        "--service-type",
        default="oil change and tire rotation",
        help="Type of service due (default: oil change and tire rotation)",
    )
    parser.add_argument("--mileage", required=True, help="Current vehicle mileage")
    args = parser.parse_args()

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "customer_name": args.name,
            "vehicle": args.vehicle,
            "service_type": args.service_type,
            "mileage": args.mileage,
        },
    )

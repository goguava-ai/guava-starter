import argparse
import json
import logging
import os
from datetime import datetime

import guava
from guava import logging_utils

agent = guava.Agent(
    name="Jamie",
    organization="Lakeside Auto Group",
    purpose=(
        "follow up with customers after a service visit to confirm their "
        "satisfaction, address any unresolved concerns, and invite them to "
        "leave a review"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(contact_full_name=call.get_variable("customer_name"))


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    customer_name = call.get_variable("customer_name")
    vehicle = call.get_variable("vehicle")
    service_date = call.get_variable("service_date")
    service_performed = call.get_variable("service_performed")

    if outcome == "unavailable":
        logging.warning("Could not reach %s for post-service follow-up call.", customer_name)
        results = {
            "timestamp": datetime.now().isoformat(),
            "customer_name": customer_name,
            "vehicle": vehicle,
            "service_date": service_date,
            "service_performed": service_performed,
            "status": "recipient_unavailable",
        }
        print(json.dumps(results, indent=2))
        call.hangup()
    elif outcome == "available":
        call.set_task(
            "followup",
            objective=(
                f"Follow up with {customer_name} regarding their {vehicle} "
                f"that was serviced on {service_date} for {service_performed}. "
                f"Confirm they are satisfied with the work, check that the vehicle is "
                f"performing well, address any outstanding concerns, and request permission "
                f"to send a review link."
            ),
            checklist=[
                guava.Say(
                    f"Thank {customer_name} for choosing Lakeside Auto Group and "
                    f"mention their recent visit on {service_date} for "
                    f"{service_performed} on their {vehicle}."
                ),
                guava.Field(
                    key="service_satisfaction_rating",
                    description=(
                        "Customer's overall satisfaction rating for the service visit, "
                        "on a scale of 1 to 5 where 1 is very unsatisfied and 5 is very satisfied"
                    ),
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="issue_resolved",
                    description="Whether the original service issue or maintenance item was fully resolved",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="vehicle_performing_well",
                    description="Whether the vehicle has been performing well since the service visit",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="follow_up_service_needed",
                    description="Any additional service or follow-up work the customer believes is needed",
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="review_permission",
                    description=(
                        "Whether the customer gives permission to be sent a link to leave "
                        "an online review for Lakeside Auto Group"
                    ),
                    field_type="text",
                    required=True,
                ),
            ],
        )


@agent.on_task_complete("followup")
def on_followup_done(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    results = {
        "timestamp": datetime.now().isoformat(),
        "customer_name": customer_name,
        "vehicle": call.get_variable("vehicle"),
        "service_date": call.get_variable("service_date"),
        "service_performed": call.get_variable("service_performed"),
        "service_satisfaction_rating": call.get_field("service_satisfaction_rating"),
        "issue_resolved": call.get_field("issue_resolved"),
        "vehicle_performing_well": call.get_field("vehicle_performing_well"),
        "follow_up_service_needed": call.get_field("follow_up_service_needed"),
        "review_permission": call.get_field("review_permission"),
    }

    print(json.dumps(results, indent=2))
    logging.info("Post-service follow-up results collected for %s", customer_name)

    call.hangup(
        final_instructions=(
            f"Thank {customer_name} sincerely for their feedback and their "
            f"continued trust in Lakeside Auto Group. If they gave permission for a "
            f"review, let them know the link will be sent shortly. If any follow-up "
            f"service was mentioned, assure them the service team will be in touch. "
            f"Wish them a wonderful day."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound post-service follow-up call for Lakeside Auto Group"
    )
    parser.add_argument("phone", help="Customer phone number to call")
    parser.add_argument("--name", required=True, help="Customer full name")
    parser.add_argument(
        "--vehicle",
        required=True,
        help='Vehicle year, make, and model (e.g. "2021 Toyota Camry")',
    )
    parser.add_argument("--service-date", required=True, help="Date of the service visit")
    parser.add_argument(
        "--service-performed",
        default="your recent service",
        help="Description of the service performed (default: your recent service)",
    )
    args = parser.parse_args()

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "customer_name": args.name,
            "vehicle": args.vehicle,
            "service_date": args.service_date,
            "service_performed": args.service_performed,
        },
    )

import guava
import os
import logging
from guava import logging_utils
import json
import argparse
from datetime import datetime



class ServiceReminderController(guava.CallController):
    def __init__(self, customer_name, vehicle, service_type, mileage):
        super().__init__()
        self.customer_name = customer_name
        self.vehicle = vehicle
        self.service_type = service_type
        self.mileage = mileage

        self.set_persona(
            organization_name="Lakeside Auto Group",
            agent_name="Taylor",
            agent_purpose=(
                f"call customers who are due for routine maintenance and help them "
                f"book a service bay appointment for their vehicle"
            ),
        )

        self.reach_person(
            contact_full_name=self.customer_name,
            on_success=self.start_service_reminder,
            on_failure=self.recipient_unavailable,
        )

    def start_service_reminder(self):
        self.set_task(
            objective=(
                f"Remind {self.customer_name} that their {self.vehicle} is due for "
                f"{self.service_type} at {self.mileage} miles, and schedule a "
                f"service bay appointment at Lakeside Auto Group."
            ),
            checklist=[
                guava.Say(
                    f"Let {self.customer_name} know their {self.vehicle} is due for "
                    f"{self.service_type} based on their current mileage of {self.mileage}."
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
            on_complete=self.save_results,
        )

    def save_results(self):
        results = {
            "timestamp": datetime.now().isoformat(),
            "customer_name": self.customer_name,
            "vehicle": self.vehicle,
            "service_type": self.service_type,
            "mileage": self.mileage,
            "service_acknowledged": self.get_field("service_acknowledged"),
            "appointment_date_preference": self.get_field("appointment_date_preference"),
            "appointment_time_preference": self.get_field("appointment_time_preference"),
            "loaner_car_needed": self.get_field("loaner_car_needed"),
            "additional_service_requests": self.get_field("additional_service_requests"),
        }

        print(json.dumps(results, indent=2))
        logging.info("Service reminder results collected for %s", self.customer_name)

        self.hangup(
            final_instructions=(
                f"Thank {self.customer_name} for their time, confirm their appointment "
                f"details, and let them know that Lakeside Auto Group will send a "
                f"confirmation. Wish them a great day."
            )
        )

    def recipient_unavailable(self):
        logging.warning("Could not reach %s for service reminder call.", self.customer_name)
        results = {
            "timestamp": datetime.now().isoformat(),
            "customer_name": self.customer_name,
            "vehicle": self.vehicle,
            "service_type": self.service_type,
            "mileage": self.mileage,
            "status": "recipient_unavailable",
        }
        print(json.dumps(results, indent=2))


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

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=ServiceReminderController(
            customer_name=args.name,
            vehicle=args.vehicle,
            service_type=args.service_type,
            mileage=args.mileage,
        ),
    )

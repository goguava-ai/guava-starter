import guava
import os
import logging
from guava import logging_utils
import json
import argparse
from datetime import datetime



class PostServiceFollowupController(guava.CallController):
    def __init__(self, customer_name, vehicle, service_date, service_performed):
        super().__init__()
        self.customer_name = customer_name
        self.vehicle = vehicle
        self.service_date = service_date
        self.service_performed = service_performed

        self.set_persona(
            organization_name="Lakeside Auto Group",
            agent_name="Jamie",
            agent_purpose=(
                "follow up with customers after a service visit to confirm their "
                "satisfaction, address any unresolved concerns, and invite them to "
                "leave a review"
            ),
        )

        self.reach_person(
            contact_full_name=self.customer_name,
            on_success=self.start_followup,
            on_failure=self.recipient_unavailable,
        )

    def start_followup(self):
        self.set_task(
            objective=(
                f"Follow up with {self.customer_name} regarding their {self.vehicle} "
                f"that was serviced on {self.service_date} for {self.service_performed}. "
                f"Confirm they are satisfied with the work, check that the vehicle is "
                f"performing well, address any outstanding concerns, and request permission "
                f"to send a review link."
            ),
            checklist=[
                guava.Say(
                    f"Thank {self.customer_name} for choosing Lakeside Auto Group and "
                    f"mention their recent visit on {self.service_date} for "
                    f"{self.service_performed} on their {self.vehicle}."
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
            on_complete=self.save_results,
        )

    def save_results(self):
        results = {
            "timestamp": datetime.now().isoformat(),
            "customer_name": self.customer_name,
            "vehicle": self.vehicle,
            "service_date": self.service_date,
            "service_performed": self.service_performed,
            "service_satisfaction_rating": self.get_field("service_satisfaction_rating"),
            "issue_resolved": self.get_field("issue_resolved"),
            "vehicle_performing_well": self.get_field("vehicle_performing_well"),
            "follow_up_service_needed": self.get_field("follow_up_service_needed"),
            "review_permission": self.get_field("review_permission"),
        }

        print(json.dumps(results, indent=2))
        logging.info("Post-service follow-up results collected for %s", self.customer_name)

        self.hangup(
            final_instructions=(
                f"Thank {self.customer_name} sincerely for their feedback and their "
                f"continued trust in Lakeside Auto Group. If they gave permission for a "
                f"review, let them know the link will be sent shortly. If any follow-up "
                f"service was mentioned, assure them the service team will be in touch. "
                f"Wish them a wonderful day."
            )
        )

    def recipient_unavailable(self):
        logging.warning("Could not reach %s for post-service follow-up call.", self.customer_name)
        results = {
            "timestamp": datetime.now().isoformat(),
            "customer_name": self.customer_name,
            "vehicle": self.vehicle,
            "service_date": self.service_date,
            "service_performed": self.service_performed,
            "status": "recipient_unavailable",
        }
        print(json.dumps(results, indent=2))


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

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=PostServiceFollowupController(
            customer_name=args.name,
            vehicle=args.vehicle,
            service_date=args.service_date,
            service_performed=args.service_performed,
        ),
    )

import guava
import os
import logging
import json
import argparse
from datetime import datetime

logging.basicConfig(level=logging.INFO)


class RecallNotificationController(guava.CallController):
    def __init__(self, customer_name, vehicle, recall_number, recall_description):
        super().__init__()
        self.customer_name = customer_name
        self.vehicle = vehicle
        self.recall_number = recall_number
        self.recall_description = recall_description

        self.set_persona(
            organization_name="Lakeside Auto Group - Safety Team",
            agent_name="Morgan",
            agent_purpose=(
                "notify vehicle owners about open safety recalls and collect their "
                "scheduling preferences so the required repair can be completed"
            ),
        )

        self.reach_person(
            contact_full_name=self.customer_name,
            on_success=self.start_recall_notification,
            on_failure=self.recipient_unavailable,
        )

    def start_recall_notification(self):
        self.set_task(
            objective=(
                f"Inform {self.customer_name} that their {self.vehicle} is affected by "
                f"safety recall {self.recall_number} ({self.recall_description}). "
                f"Confirm they are aware, verify they still have the vehicle, and collect "
                f"scheduling preferences so Lakeside Auto Group can complete the repair at "
                f"no charge."
            ),
            checklist=[
                guava.Say(
                    f"Notify {self.customer_name} that their {self.vehicle} has an open "
                    f"safety recall (Recall #{self.recall_number}) related to: "
                    f"{self.recall_description}. Emphasize the repair is free of charge."
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
            on_complete=self.save_results,
        )

    def save_results(self):
        results = {
            "timestamp": datetime.now().isoformat(),
            "customer_name": self.customer_name,
            "vehicle": self.vehicle,
            "recall_number": self.recall_number,
            "recall_description": self.recall_description,
            "recall_acknowledged": self.get_field("recall_acknowledged"),
            "vehicle_in_possession": self.get_field("vehicle_in_possession"),
            "appointment_date_preference": self.get_field("appointment_date_preference"),
            "transportation_needed": self.get_field("transportation_needed"),
            "questions_about_recall": self.get_field("questions_about_recall"),
        }

        print(json.dumps(results, indent=2))
        logging.info("Recall notification results collected for %s", self.customer_name)

        self.hangup(
            final_instructions=(
                f"Thank {self.customer_name} for their time. Reassure them that the recall "
                f"repair is straightforward and completely free. Confirm their appointment "
                f"preference has been noted and that someone from the service team will be "
                f"in touch with a confirmed time. Wish them a safe and pleasant day."
            )
        )

    def recipient_unavailable(self):
        logging.warning("Could not reach %s for recall notification call.", self.customer_name)
        results = {
            "timestamp": datetime.now().isoformat(),
            "customer_name": self.customer_name,
            "vehicle": self.vehicle,
            "recall_number": self.recall_number,
            "recall_description": self.recall_description,
            "status": "recipient_unavailable",
        }
        print(json.dumps(results, indent=2))


if __name__ == "__main__":
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

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=RecallNotificationController(
            customer_name=args.name,
            vehicle=args.vehicle,
            recall_number=args.recall_number,
            recall_description=args.recall_description,
        ),
    )

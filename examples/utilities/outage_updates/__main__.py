import guava
import os
import logging
import json
import argparse
from datetime import datetime

logging.basicConfig(level=logging.INFO)


class OutageUpdateController(guava.CallController):
    def __init__(self, account_number, outage_cause, estimated_restoration):
        super().__init__()
        self.account_number = account_number
        self.outage_cause = outage_cause
        self.estimated_restoration = estimated_restoration

        self.set_persona(
            organization_name="Metro Power & Light",
            agent_name="Alex",
            agent_purpose=(
                "notify customers about an active power outage affecting their area, "
                "provide status information and the estimated restoration time, "
                "and check on any special needs the customer may have during the outage"
            ),
        )

        self.set_task(
            objective=(
                f"Inform the customer that their account ({self.account_number}) is "
                f"affected by a power outage caused by {self.outage_cause}. "
                f"Let them know that power is estimated to be restored {self.estimated_restoration}. "
                "Confirm they received the update and check whether they have any special needs "
                "such as medical equipment dependency, access to a generator, or need for an "
                "alternate location while power is out."
            ),
            checklist=[
                guava.Say(
                    f"Hello, this is Alex calling from Metro Power & Light with an important "
                    f"service update for account {self.account_number}. We are currently "
                    f"experiencing a power outage in your area due to {self.outage_cause}. "
                    f"Our crews are working to restore service and we estimate power will be "
                    f"restored {self.estimated_restoration}. We apologize for the inconvenience."
                ),
                guava.Field(
                    key="outage_acknowledged",
                    description="Confirm the customer acknowledges they have received the outage notification and understands the estimated restoration time",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="medical_equipment_dependent",
                    description="Ask whether anyone in the household relies on electrically powered medical equipment such as oxygen concentrators, home dialysis machines, or other life-sustaining devices",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="generator_available",
                    description="Ask whether the customer has a generator or backup power source available to use during the outage",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="alternate_location_needed",
                    description="Ask whether the customer needs assistance finding an alternate location such as a warming or cooling center while power is restored",
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="additional_concerns",
                    description="Ask if the customer has any other concerns or questions about the outage or their service",
                    field_type="text",
                    required=False,
                ),
            ],
            on_complete=self.save_results,
        )

    def save_results(self):
        results = {
            "timestamp": datetime.now().isoformat(),
            "account_number": self.account_number,
            "outage_cause": self.outage_cause,
            "estimated_restoration": self.estimated_restoration,
            "fields": {
                "outage_acknowledged": self.get_field("outage_acknowledged"),
                "medical_equipment_dependent": self.get_field("medical_equipment_dependent"),
                "generator_available": self.get_field("generator_available"),
                "alternate_location_needed": self.get_field("alternate_location_needed"),
                "additional_concerns": self.get_field("additional_concerns"),
            },
        }
        print(json.dumps(results, indent=2))
        self.hangup(
            final_instructions=(
                "Thank the customer for their time and patience during the outage. "
                "Remind them that Metro Power & Light crews are working as quickly and safely "
                "as possible to restore service. Let them know they can track outage status "
                "at metropowerandlight.com or by calling our outage hotline. Wish them well."
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Metro Power & Light — Outage Update Notification"
    )
    parser.add_argument("phone", help="Customer phone number to call")
    parser.add_argument("--account-number", required=True, help="Customer account number")
    parser.add_argument(
        "--outage-cause",
        default="an equipment issue in your area",
        help="Description of the cause of the outage",
    )
    parser.add_argument(
        "--estimated-restoration",
        default="by 6:00 PM today",
        help="Estimated power restoration time (e.g. 'by 6:00 PM today')",
    )
    args = parser.parse_args()

    controller = OutageUpdateController(
        account_number=args.account_number,
        outage_cause=args.outage_cause,
        estimated_restoration=args.estimated_restoration,
    )

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=controller,
    )

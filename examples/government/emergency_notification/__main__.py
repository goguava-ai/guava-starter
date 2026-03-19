import guava
import os
import logging
import json
import argparse
from datetime import datetime

logging.basicConfig(level=logging.INFO)


class EmergencyNotificationController(guava.CallController):
    def __init__(self, alert_type: str, instructions: str):
        super().__init__()
        self.alert_type = alert_type
        self.instructions = instructions
        self.set_persona(
            organization_name="Springfield Emergency Management",
            agent_name="Morgan",
            agent_purpose=(
                f"deliver an urgent {self.alert_type} notification to residents and "
                "collect structured confirmation of acknowledgement and any immediate needs"
            ),
        )
        self.set_task(
            objective=(
                f"You are calling on behalf of Springfield Emergency Management to deliver "
                f"an urgent public safety alert regarding a {self.alert_type}. "
                f"The instructions for residents are: {self.instructions}. "
                "Deliver the alert clearly and calmly. Do not cause unnecessary panic, "
                "but convey the seriousness of the situation. Collect confirmation that "
                "the resident has received the alert and gather information about any "
                "immediate assistance needs."
            ),
            checklist=[
                guava.Say(
                    f"IMPORTANT MESSAGE from Springfield Emergency Management. "
                    f"This is an automated emergency notification. There is currently a "
                    f"{self.alert_type} affecting your area. "
                    f"{self.instructions}. "
                    "Please listen carefully. I have a few brief questions to confirm "
                    "you have received this alert and to determine if you need any assistance."
                ),
                guava.Field(
                    key="alert_acknowledged",
                    description=(
                        "Confirm that the resident has heard and understood the emergency alert "
                        "and the instructions provided."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="evacuation_assistance_needed",
                    description=(
                        "Ask whether the resident or anyone in their household needs "
                        "assistance with evacuation or transportation to a safe location."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="household_members_count",
                    description=(
                        "If the resident may need assistance, ask how many people are "
                        "currently in the household so responders can plan accordingly."
                    ),
                    field_type="integer",
                    required=False,
                ),
                guava.Field(
                    key="special_needs_or_pets",
                    description=(
                        "Ask whether anyone in the household has special medical needs, "
                        "mobility limitations, or pets that would require specific "
                        "accommodations during evacuation or sheltering."
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="current_location_safe",
                    description=(
                        "Ask whether the resident currently considers their location safe "
                        "based on the emergency alert they just received."
                    ),
                    field_type="text",
                    required=True,
                ),
            ],
            on_complete=self.save_results,
        )

    def save_results(self):
        results = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "alert_type": self.alert_type,
            "instructions": self.instructions,
            "fields": {
                "alert_acknowledged": self.get_field("alert_acknowledged"),
                "evacuation_assistance_needed": self.get_field("evacuation_assistance_needed"),
                "household_members_count": self.get_field("household_members_count"),
                "special_needs_or_pets": self.get_field("special_needs_or_pets"),
                "current_location_safe": self.get_field("current_location_safe"),
            },
        }
        print(json.dumps(results, indent=2))
        self.hangup(
            final_instructions=(
                "Close the call by reiterating the most critical action the resident should "
                "take based on the alert instructions. If the resident indicated they need "
                "evacuation assistance, assure them that their information has been noted and "
                "that emergency services are aware of their need. Direct them to tune in to "
                "local emergency broadcasts or visit the Springfield Emergency Management "
                "website for updates. End the call quickly and clearly so the resident can "
                "take action."
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Outbound emergency notification call for Springfield Emergency Management."
    )
    parser.add_argument("phone", help="Resident phone number to call (E.164 format).")
    parser.add_argument(
        "--alert-type",
        required=True,
        help='Type of emergency alert (e.g., "tornado warning", "flash flood warning", "evacuation order").',
    )
    parser.add_argument(
        "--instructions",
        required=True,
        help="Specific instructions for residents to follow in response to the alert.",
    )
    args = parser.parse_args()

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=EmergencyNotificationController(
            alert_type=args.alert_type,
            instructions=args.instructions,
        ),
    )

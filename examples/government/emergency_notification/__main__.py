import guava
import os
import logging
from guava import logging_utils
import json
import argparse
from datetime import datetime, timezone


agent = guava.Agent(
    name="Morgan",
    organization="Springfield Emergency Management",
    purpose=(
        "deliver an urgent emergency notification to residents and "
        "collect structured confirmation of acknowledgement and any immediate needs"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    alert_type = call.get_variable("alert_type")
    instructions = call.get_variable("instructions")
    call.set_task(
        "notification",
        objective=(
            f"You are calling on behalf of Springfield Emergency Management to deliver "
            f"an urgent public safety alert regarding a {alert_type}. "
            f"The instructions for residents are: {instructions}. "
            "Deliver the alert clearly and calmly. Do not cause unnecessary panic, "
            "but convey the seriousness of the situation. Collect confirmation that "
            "the resident has received the alert and gather information about any "
            "immediate assistance needs."
        ),
        checklist=[
            guava.Say(
                f"IMPORTANT MESSAGE from Springfield Emergency Management. "
                f"This is an automated emergency notification. There is currently a "
                f"{alert_type} affecting your area. "
                f"{instructions}. "
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
    )


@agent.on_task_complete("notification")
def on_done(call: guava.Call) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "alert_type": call.get_variable("alert_type"),
        "instructions": call.get_variable("instructions"),
        "fields": {
            "alert_acknowledged": call.get_field("alert_acknowledged"),
            "evacuation_assistance_needed": call.get_field("evacuation_assistance_needed"),
            "household_members_count": call.get_field("household_members_count"),
            "special_needs_or_pets": call.get_field("special_needs_or_pets"),
            "current_location_safe": call.get_field("current_location_safe"),
        },
    }
    print(json.dumps(results, indent=2))
    call.hangup(
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
    logging_utils.configure_logging()
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

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "alert_type": args.alert_type,
            "instructions": args.instructions,
        },
    )

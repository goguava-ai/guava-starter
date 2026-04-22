import guava
import os
import logging
from guava import logging_utils
import json
import argparse
from datetime import datetime, timezone



class CancellationWinbackController(guava.CallController):
    def __init__(self, name, reservation_number, original_dates, room_type):
        super().__init__()
        self.name = name
        self.reservation_number = reservation_number
        self.original_dates = original_dates
        self.room_type = room_type

        self.set_persona(
            organization_name="The Grand Meridian Hotel",
            agent_name="Sophie",
            agent_purpose=(
                "reach out to a guest who recently cancelled their reservation, understand the "
                "reason behind the decision with empathy, explore whether alternative arrangements "
                "might better suit their needs, and warmly invite them to rebook"
            ),
        )

        self.reach_person(
            contact_full_name=self.name,
            on_success=self.begin_winback,
            on_failure=self.recipient_unavailable,
        )

    def begin_winback(self):
        self.set_task(
            objective=(
                f"You are calling {self.name} regarding the recent cancellation of reservation "
                f"{self.reservation_number} for {self.room_type}, originally booked for {self.original_dates}. "
                "Approach the conversation with genuine care and zero pressure. Begin by acknowledging "
                "the cancellation and expressing that the hotel would love to understand what happened. "
                "Listen to the guest's reason with empathy, then thoughtfully explore whether alternative "
                "dates, a room upgrade, or a special offer might address their concerns. Conclude by "
                "understanding where the guest stands on potentially rebooking."
            ),
            checklist=[
                guava.Say(
                    f"Greet {self.name} warmly and acknowledge the cancellation of their reservation "
                    f"for {self.original_dates}. Express genuine regret that the plans changed and let "
                    "them know you are calling simply to understand if there is anything the hotel can do."
                ),
                guava.Field(
                    key="cancellation_reason",
                    description=(
                        "What was the primary reason the guest decided to cancel their reservation? "
                        "Listen carefully and capture the response in full."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="open_to_alternative_dates",
                    description=(
                        "Is the guest open to exploring alternative dates for their stay, "
                        "or are their travel plans no longer possible?"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="alternative_date_preference",
                    description=(
                        "If the guest is open to rebooking, what date range or specific dates "
                        "would work best for them?"
                    ),
                    field_type="date",
                    required=False,
                ),
                guava.Field(
                    key="discount_or_upgrade_motivating",
                    description=(
                        "Would a special rate, complimentary upgrade, or added amenity make "
                        "rebooking more appealing to the guest?"
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="rebooking_decision",
                    description=(
                        "What is the guest's current decision regarding rebooking? "
                        "For example: confirmed interest, would like to think about it, or not interested."
                    ),
                    field_type="text",
                    required=True,
                ),
            ],
            on_complete=self.save_results,
        )

    def save_results(self):
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "use_case": "cancellation_winback",
            "guest_name": self.name,
            "reservation_number": self.reservation_number,
            "original_dates": self.original_dates,
            "room_type": self.room_type,
            "fields": {
                "cancellation_reason": self.get_field("cancellation_reason"),
                "open_to_alternative_dates": self.get_field("open_to_alternative_dates"),
                "alternative_date_preference": self.get_field("alternative_date_preference"),
                "discount_or_upgrade_motivating": self.get_field("discount_or_upgrade_motivating"),
                "rebooking_decision": self.get_field("rebooking_decision"),
            },
        }
        print(json.dumps(results, indent=2))
        logging.info("Cancellation winback results saved for %s", self.name)
        self.hangup(
            final_instructions=(
                f"Close the call warmly and graciously, regardless of the guest's rebooking decision. "
                f"Thank {self.name} for their time and for speaking openly. If they expressed interest "
                "in rebooking, let them know a reservations team member will follow up with tailored options. "
                "If they declined, wish them well and leave the door open for a future stay. Never push or pressure."
            )
        )

    def recipient_unavailable(self):
        logging.warning("Could not reach %s for cancellation winback call.", self.name)
        self.hangup(
            final_instructions=(
                "Leave a thoughtful voicemail as Sophie from The Grand Meridian Hotel, acknowledging "
                "the recent cancellation and expressing that the hotel would love to understand if there "
                "is anything they can do to help. Invite the guest to call back at their convenience and "
                "mention that the reservations team would be happy to explore flexible options."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound cancellation winback call — The Grand Meridian Hotel"
    )
    parser.add_argument("phone", help="Guest phone number to call")
    parser.add_argument("--name", required=True, help="Full name of the guest")
    parser.add_argument("--reservation-number", required=True, help="Cancelled reservation reference number")
    parser.add_argument("--original-dates", required=True, help="Original stay dates that were cancelled")
    parser.add_argument(
        "--room-type", default="your room", help="Room type that was booked (default: your room)"
    )
    args = parser.parse_args()

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=CancellationWinbackController(
            name=args.name,
            reservation_number=args.reservation_number,
            original_dates=args.original_dates,
            room_type=args.room_type,
        ),
    )

import guava
import os
import logging
from guava import logging_utils
import json
import argparse
from datetime import datetime, timezone



class ReservationConfirmationController(guava.CallController):
    def __init__(self, name, reservation_number, checkin_date, room_type):
        super().__init__()
        self.name = name
        self.reservation_number = reservation_number
        self.checkin_date = checkin_date
        self.room_type = room_type

        self.set_persona(
            organization_name="The Grand Meridian Hotel",
            agent_name="Sophie",
            agent_purpose=(
                "confirm an upcoming reservation, share any available upgrade options, "
                "and ensure the guest's arrival is as seamless and enjoyable as possible"
            ),
        )

        self.reach_person(
            contact_full_name=self.name,
            on_success=self.begin_confirmation,
            on_failure=self.recipient_unavailable,
        )

    def begin_confirmation(self):
        self.set_task(
            objective=(
                f"You are confirming reservation {self.reservation_number} for {self.name}, "
                f"checking in on {self.checkin_date} in a {self.room_type}. "
                "Warmly confirm the booking details, then graciously invite the guest to consider "
                "available enhancements such as a room upgrade, early check-in, or add-on packages. "
                "Collect the guest's preferences in a conversational, unhurried manner befitting a "
                "luxury hotel experience."
            ),
            checklist=[
                guava.Say(
                    f"Warmly greet {self.name} and confirm their reservation number "
                    f"{self.reservation_number} for check-in on {self.checkin_date} in a {self.room_type}."
                ),
                guava.Field(
                    key="booking_confirmed",
                    description="Has the guest confirmed their booking details are correct?",
                    field_type="text",
                    required=True,
                ),
                guava.Say(
                    "Let the guest know about available room upgrades and briefly describe the benefits, "
                    "such as enhanced views, additional space, or premium amenities."
                ),
                guava.Field(
                    key="upgrade_interest",
                    description="Is the guest interested in a room upgrade? If so, what type?",
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="early_checkin_requested",
                    description="Would the guest like to request early check-in?",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="special_occasion",
                    description=(
                        "Is the guest celebrating a special occasion during their stay, "
                        "such as an anniversary, birthday, or honeymoon?"
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="parking_needed",
                    description="Will the guest require parking during their stay?",
                    field_type="text",
                    required=True,
                ),
            ],
            on_complete=self.save_results,
        )

    def save_results(self):
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "use_case": "reservation_confirmation",
            "guest_name": self.name,
            "reservation_number": self.reservation_number,
            "checkin_date": self.checkin_date,
            "room_type": self.room_type,
            "fields": {
                "booking_confirmed": self.get_field("booking_confirmed"),
                "upgrade_interest": self.get_field("upgrade_interest"),
                "early_checkin_requested": self.get_field("early_checkin_requested"),
                "special_occasion": self.get_field("special_occasion"),
                "parking_needed": self.get_field("parking_needed"),
            },
        }
        print(json.dumps(results, indent=2))
        logging.info("Reservation confirmation results saved for %s", self.name)
        self.hangup(
            final_instructions=(
                f"Thank {self.name} sincerely for their time and express genuine excitement about "
                "welcoming them to The Grand Meridian Hotel. Let them know that any further requests "
                "can be directed to the concierge team, and wish them a wonderful day."
            )
        )

    def recipient_unavailable(self):
        logging.warning("Could not reach %s for reservation confirmation.", self.name)
        self.hangup(
            final_instructions=(
                "Leave a warm, professional voicemail introducing yourself as Sophie from "
                "The Grand Meridian Hotel, referencing the upcoming reservation, and inviting "
                "the guest to call back at their convenience."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound reservation confirmation call — The Grand Meridian Hotel"
    )
    parser.add_argument("phone", help="Guest phone number to call")
    parser.add_argument("--name", required=True, help="Full name of the guest")
    parser.add_argument("--reservation-number", required=True, help="Reservation reference number")
    parser.add_argument("--checkin-date", required=True, help="Scheduled check-in date")
    parser.add_argument(
        "--room-type", default="standard room", help="Room type booked (default: standard room)"
    )
    args = parser.parse_args()

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=ReservationConfirmationController(
            name=args.name,
            reservation_number=args.reservation_number,
            checkin_date=args.checkin_date,
            room_type=args.room_type,
        ),
    )

import argparse
import json
import logging
import os
from datetime import datetime, timezone

import guava
from guava import logging_utils

agent = guava.Agent(
    name="Sophie",
    organization="The Grand Meridian Hotel",
    purpose=(
        "confirm an upcoming reservation, share any available upgrade options, "
        "and ensure the guest's arrival is as seamless and enjoyable as possible"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(contact_full_name=call.get_variable("name"))


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    if outcome == "unavailable":
        logging.warning("Could not reach %s for reservation confirmation.", call.get_variable("name"))
        call.hangup(
            final_instructions=(
                "Leave a warm, professional voicemail introducing yourself as Sophie from "
                "The Grand Meridian Hotel, referencing the upcoming reservation, and inviting "
                "the guest to call back at their convenience."
            )
        )
    elif outcome == "available":
        call.set_task(
            "reservation_confirmation",
            objective=(
                f"You are confirming reservation {call.get_variable('reservation_number')} for {call.get_variable('name')}, "
                f"checking in on {call.get_variable('checkin_date')} in a {call.get_variable('room_type')}. "
                "Warmly confirm the booking details, then graciously invite the guest to consider "
                "available enhancements such as a room upgrade, early check-in, or add-on packages. "
                "Collect the guest's preferences in a conversational, unhurried manner befitting a "
                "luxury hotel experience."
            ),
            checklist=[
                guava.Say(
                    f"Warmly greet {call.get_variable('name')} and confirm their reservation number "
                    f"{call.get_variable('reservation_number')} for check-in on {call.get_variable('checkin_date')} in a {call.get_variable('room_type')}."
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
        )


@agent.on_task_complete("reservation_confirmation")
def on_done(call: guava.Call) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "use_case": "reservation_confirmation",
        "guest_name": call.get_variable("name"),
        "reservation_number": call.get_variable("reservation_number"),
        "checkin_date": call.get_variable("checkin_date"),
        "room_type": call.get_variable("room_type"),
        "fields": {
            "booking_confirmed": call.get_field("booking_confirmed"),
            "upgrade_interest": call.get_field("upgrade_interest"),
            "early_checkin_requested": call.get_field("early_checkin_requested"),
            "special_occasion": call.get_field("special_occasion"),
            "parking_needed": call.get_field("parking_needed"),
        },
    }
    print(json.dumps(results, indent=2))
    logging.info("Reservation confirmation results saved for %s", call.get_variable("name"))
    call.hangup(
        final_instructions=(
            f"Thank {call.get_variable('name')} sincerely for their time and express genuine excitement about "
            "welcoming them to The Grand Meridian Hotel. Let them know that any further requests "
            "can be directed to the concierge team, and wish them a wonderful day."
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

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "name": args.name,
            "reservation_number": args.reservation_number,
            "checkin_date": args.checkin_date,
            "room_type": args.room_type,
        },
    )

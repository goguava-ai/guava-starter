# SDK conformance: guava-sdk 0.42.0 (2026-09-08)
import argparse
import json
import logging
import os
from datetime import datetime, timezone

import guava
from guava import logging_utils
from guava.helpers.llm import IntentRecognizer
from guava.events import BotSessionEnded, OutboundCallFailed

agent = guava.Agent(
    name="Blake",
    organization="The Grand Meridian Hotel",
    purpose=(
        "confirm an upcoming reservation with the guest, verify the details "
        "are correct, and assist with any modifications to dates, room type, "
        "or add-on packages"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
    "speak_to_someone": "The caller wants to speak to the reservations team or a real person",
})


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(
        contact_full_name=call.get_variable("guest_name"),
        voicemail_message=(
            f"Hi, this is Blake from The Grand Meridian Hotel calling for "
            f"{call.get_variable('guest_name')}. We're reaching out to confirm "
            f"your upcoming reservation. Please call us back at your convenience. "
            f"Thank you!"
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    guest_name = call.get_variable("guest_name")
    reservation_number = call.get_variable("reservation_number")
    checkin_date = call.get_variable("checkin_date")
    room_type = call.get_variable("room_type")

    if outcome == "available":
        call.set_task(
            "confirm_reservation",
            objective=(
                f"Confirm reservation {reservation_number} for {guest_name}, "
                f"checking in on {checkin_date} in a {room_type}. Verify the "
                f"details are correct and ask if they would like to make any "
                f"modifications. Be warm and professional."
            ),
            checklist=[
                guava.Say(
                    f"I'm calling to confirm your reservation — reservation "
                    f"{reservation_number}, checking in on {checkin_date} in a "
                    f"{room_type}. Does everything look right?"
                ),
                guava.Field(
                    key="details_confirmed",
                    description="Whether the guest confirms the reservation details are correct",
                    field_type="multiple_choice",
                    choices=["confirmed", "needs_changes"],
                    required=True,
                ),
            ],
        )
    elif outcome == "do_not_contact":
        logging.info("Guest %s requested no further contact.", guest_name)
        call.hangup(
            final_instructions=(
                "Acknowledge their request graciously. Let them know they will "
                "not be contacted again, and wish them well, and politely say goodbye."
            )
        )
    elif outcome == "wrong_number":
        logging.info("Wrong number for %s.", guest_name)
        call.hangup(final_instructions="Apologize for the mistake and wish them well, and politely say goodbye.")
    else:
        logging.info("Could not reach %s (outcome: %s).", guest_name, outcome)
        call.hangup()


@agent.on_task_complete("confirm_reservation")
def on_reservation_confirmed(call: guava.Call) -> None:
    guest_name = call.get_variable("guest_name")
    confirmed = call.get_field("details_confirmed")

    if confirmed == "confirmed":
        call.hangup(
            final_instructions=(
                f"Thank {guest_name} for confirming. Express excitement about "
                f"welcoming them. Let them know any further requests can be "
                f"directed to the concierge team, and wish them a wonderful day, and politely say goodbye."
            )
        )
    else:
        call.set_task(
            "collect_modification",
            objective=(
                f"{guest_name} would like to make changes to their reservation. "
                f"Determine what type of modification they need — date change, "
                f"room type change, add-on packages, or something else."
            ),
            checklist=[
                guava.Field(
                    key="modification_type",
                    description=(
                        "The type of modification the guest would like to make "
                        "to their reservation"
                    ),
                    field_type="multiple_choice",
                    choices=["date_change", "room_type", "add_ons", "other"],
                    required=True,
                ),
                guava.Field(
                    key="modification_details",
                    description=(
                        "The specific details of the modification requested. "
                        "For date changes: what new dates they prefer. "
                        "For room type: what type they would like instead. "
                        "For add-ons: which packages interest them (spa, dining, "
                        "airport transfer, celebration setup). "
                        "For other: what they need."
                    ),
                    field_type="text",
                    required=True,
                ),
            ],
        )


@agent.on_task_complete("collect_modification")
def on_modification_collected(call: guava.Call) -> None:
    guest_name = call.get_variable("guest_name")
    mod_type = call.get_field("modification_type")
    mod_details = call.get_field("modification_details")

    if mod_type == "date_change":
        call.hangup(
            final_instructions=(
                f"Let {guest_name} know the reservations team will check "
                f"availability for their preferred dates and send a confirmation "
                f"within 24 hours. Thank them for letting the hotel know, and politely say goodbye."
            )
        )
    elif mod_type == "room_type":
        call.hangup(
            final_instructions=(
                f"Let {guest_name} know the reservations team will check "
                f"availability for their preferred room type and follow up "
                f"within 24 hours with options and pricing. Thank them, and politely say goodbye."
            )
        )
    elif mod_type == "add_ons":
        call.hangup(
            final_instructions=(
                f"Let {guest_name} know the concierge team will prepare details "
                f"on the requested packages and send them a personalized offer "
                f"within 24 hours. Thank them for their interest, and politely say goodbye."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Let {guest_name} know the reservations team will review their "
                f"request and follow up within 24 hours. Thank them for reaching "
                f"out, and wish them a wonderful day, and politely say goodbye."
            )
        )


@agent.on_action_request
def on_action_request(call: guava.Call, intent_summary: str):
    return _mid_call_intent.classify(intent_summary)


@agent.on_action("do_not_contact")
def handle_dnc(call: guava.Call) -> None:
    logging.info("Guest %s requested DNC mid-call.", call.get_variable("guest_name"))
    call.hangup(
        final_instructions=(
            "Acknowledge their request. Let them know they have been removed "
            "from the contact list and will not be called again, and wish them well, and politely say goodbye."
        )
    )


@agent.on_action("speak_to_someone")
def handle_speak_to_someone(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            "Let them know a member of the reservations team will call them "
            "back within one business day. Ask if there is a preferred time "
            "and thank them, and politely say goodbye."
        )
    )


@agent.on_outbound_failed
def on_outbound_failed(event: OutboundCallFailed) -> None:
    logging.error("Outbound call failed: %s (code %d)", event.error_reason, event.error_code)


@agent.on_session_end
def on_session_end(call: guava.Call, event: BotSessionEnded) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "use_case": "reservation_confirmation",
        "guest_name": call.get_variable("guest_name"),
        "reservation_number": call.get_variable("reservation_number"),
        "checkin_date": call.get_variable("checkin_date"),
        "room_type": call.get_variable("room_type"),
        "details_confirmed": call.get_field("details_confirmed"),
        "modification_type": call.get_field("modification_type"),
        "modification_details": call.get_field("modification_details"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


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
        "--room-type",
        default="standard room",
        help="Room type booked (default: standard room)",
    )
    parser.add_argument(
        "--from-number",
        default=os.environ.get("GUAVA_AGENT_NUMBER", ""),
        help="Caller ID / from number (defaults to GUAVA_AGENT_NUMBER env var).",
    )
    args = parser.parse_args()

    agent.call_phone(
        from_number=args.from_number,
        to_number=args.phone,
        variables={
            "guest_name": args.name,
            "reservation_number": args.reservation_number,
            "checkin_date": args.checkin_date,
            "room_type": args.room_type,
        },
    )

# SDK conformance: guava-sdk 0.38.0 (2026-08-11)
import argparse
import json
import logging
import os
from datetime import datetime, timezone

import guava
from guava import logging_utils
from guava.helpers.llm import DatetimeFilter, IntentRecognizer
from guava.events import BotSessionEnded, OutboundCallFailed


# ---------------------------------------------------------------------------
# Mock API — simulates a calendar/availability backend for demo purposes
# ---------------------------------------------------------------------------

MOCK_CLIENTS = {
    "CLT-5001": {
        "client_name": "Maria Santos",
        "dob": "1985-03-14",
        "matter_number": "HAR-2026-0301",
        "attorney": "Janet Hargrove",
    },
    "CLT-5002": {
        "client_name": "David Park",
        "dob": "1992-07-22",
        "matter_number": "HAR-2026-0415",
        "attorney": "Robert Chen",
    },
    "CLT-5003": {
        "client_name": "Rachel Kim",
        "dob": "1978-11-05",
        "matter_number": "HAR-2026-0220",
        "attorney": "Janet Hargrove",
    },
}

MOCK_AVAILABILITY = [
    {"date": "2026-07-28", "time": "09:00 AM", "attorney": "Janet Hargrove", "duration": "30 min"},
    {"date": "2026-07-28", "time": "02:00 PM", "attorney": "Janet Hargrove", "duration": "30 min"},
    {"date": "2026-07-29", "time": "10:00 AM", "attorney": "Janet Hargrove", "duration": "30 min"},
    {"date": "2026-07-29", "time": "11:00 AM", "attorney": "Robert Chen", "duration": "30 min"},
    {"date": "2026-07-29", "time": "03:00 PM", "attorney": "Robert Chen", "duration": "30 min"},
    {"date": "2026-07-30", "time": "09:30 AM", "attorney": "Janet Hargrove", "duration": "30 min"},
    {"date": "2026-07-30", "time": "01:00 PM", "attorney": "Robert Chen", "duration": "30 min"},
    {"date": "2026-07-31", "time": "10:00 AM", "attorney": "Janet Hargrove", "duration": "30 min"},
    {"date": "2026-07-31", "time": "02:30 PM", "attorney": "Robert Chen", "duration": "30 min"},
]


def _slot_to_iso(slot: dict) -> str:
    return datetime.strptime(f"{slot['date']} {slot['time']}", "%Y-%m-%d %I:%M %p").isoformat()


_SLOTS_BY_ISO = {_slot_to_iso(slot): slot for slot in MOCK_AVAILABILITY}

datetime_filter = DatetimeFilter(source_list=list(_SLOTS_BY_ISO.keys()))


def verify_client(client_id, dob):
    client = MOCK_CLIENTS.get(client_id)
    if client and client["dob"] == dob:
        return client
    return None


def book_appointment(attorney, date, time_slot):
    logging.info(
        "[MOCK API] POST /appointments — booked %s on %s at %s",
        attorney, date, time_slot,
    )
    return f"APT-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}"


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

agent = guava.Agent(
    name="Finley",
    organization="Hargrove & Associates Law Firm",
    purpose=(
        "verify an existing client's identity, present available appointment "
        "times with their attorney, and confirm a booking"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
    "speak_to_someone": "The caller wants to speak to their attorney or a staff member directly",
})


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(
        contact_full_name=call.get_variable("contact_name"),
        voicemail_message=(
            f"Hi, this is Finley from Hargrove & Associates calling for "
            f"{call.get_variable('contact_name')}. We're reaching out to schedule "
            f"an appointment with your attorney. Please call us back at your "
            f"convenience. Thank you."
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    contact_name = call.get_variable("contact_name")

    if outcome == "available":
        call.set_task(
            "verify_client",
            objective=(
                f"Verify the identity of {contact_name} before accessing their "
                f"account or scheduling. Ask for their date of birth. Do not "
                f"discuss case details or attorney information until verified."
            ),
            checklist=[
                guava.Say(
                    f"I'm calling to schedule an appointment with your attorney. "
                    f"Before I can access your account, I need to verify your "
                    f"identity."
                ),
                guava.Field(
                    key="dob",
                    description="The client's date of birth for identity verification",
                    field_type="text",
                    required=True,
                ),
            ],
        )
    elif outcome == "do_not_contact":
        logging.info("Client %s requested no further contact.", contact_name)
        call.hangup(
            final_instructions=(
                "Acknowledge their request. Let them know they will not be contacted "
                "again by phone. They can call the firm directly to schedule, and politely say goodbye."
            )
        )
    elif outcome == "wrong_number":
        logging.info("Wrong number for %s.", contact_name)
        call.hangup(final_instructions="Apologize for the mistake and wish them well, and politely say goodbye.")
    else:
        logging.info("Could not reach %s (outcome: %s).", contact_name, outcome)
        call.hangup()


@agent.on_task_complete("verify_client")
def on_client_verified(call: guava.Call) -> None:
    client_id = call.get_variable("client_id")
    dob = call.get_field("dob")
    client = verify_client(client_id, dob)

    if client is None:
        logging.warning("Identity verification failed for client %s.", client_id)
        call.hangup(
            final_instructions=(
                "Let them know the date of birth provided does not match our records. "
                "For security, you cannot proceed. Suggest they call the firm directly "
                "with their client ID handy, and politely say goodbye."
            )
        )
        return

    contact_name = call.get_variable("contact_name")
    call.set_variable("attorney", client["attorney"])
    call.set_variable("matter_number", client["matter_number"])

    call.add_info("client_details", {
        "client_id": client_id,
        "client_name": client["client_name"],
        "attorney": client["attorney"],
        "matter_number": client["matter_number"],
    })

    call.set_task(
        "select_time",
        objective=(
            f"Identity verified — {contact_name} is a client of "
            f"{client['attorney']}. Present available appointment times and "
            f"let the client choose their preferred slot. If no times work, "
            f"ask for their preferred date range and search again."
        ),
        checklist=[
            guava.Say(
                f"Thank you, {contact_name}. You're verified. I have availability "
                f"for {client['attorney']}. Let me find some times that work for you."
            ),
            guava.Field(
                key="preferred_date_range",
                description=(
                    "The client's preferred date range for the appointment. "
                    "Use this to search for available slots."
                ),
                field_type="text",
                required=True,
                searchable=True,
            ),
            guava.Field(
                key="selected_slot",
                description=(
                    "The specific appointment slot the client has chosen, "
                    "including date and time"
                ),
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="meeting_format",
                description="Whether the client prefers in-person, phone, or video conference",
                field_type="multiple_choice",
                choices=["in_person", "phone", "video"],
                required=True,
            ),
        ],
    )


@agent.on_search_query("preferred_date_range")
def on_search_date_range(call: guava.Call, query: str):
    matching, fallback = datetime_filter.filter(query, max_results=3)

    def describe(iso: str) -> str:
        slot = _SLOTS_BY_ISO[iso]
        return f"{slot['date']} at {slot['time']} with {slot['attorney']} ({slot['duration']})"

    return [describe(iso) for iso in matching], [describe(iso) for iso in fallback]


@agent.on_task_complete("select_time")
def on_time_selected(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    attorney = call.get_variable("attorney")
    selected = call.get_field("selected_slot")

    appointment_id = book_appointment(attorney, selected, "")
    call.set_variable("appointment_id", appointment_id)

    call.set_task(
        "confirm_booking",
        objective=(
            f"Confirm the appointment booking with {contact_name}. The appointment "
            f"ID is {appointment_id}. Ask for a confirmation email address and "
            f"verify there are no special needs."
        ),
        checklist=[
            guava.Say(
                f"Your appointment has been booked. Your confirmation number is "
                f"{appointment_id}."
            ),
            guava.Field(
                key="confirmation_email",
                description="Email address for the appointment confirmation",
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="special_accommodations",
                description=(
                    "Any special accommodations needed, such as accessibility, "
                    "interpreter, or technical requirements for video"
                ),
                field_type="text",
                required=False,
            ),
        ],
    )


@agent.on_task_complete("confirm_booking")
def on_booking_confirmed(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    call.hangup(
        final_instructions=(
            f"Thank {contact_name} for scheduling. Confirm that a confirmation "
            f"email will be sent to the address they provided. Let them know they "
            f"can call the firm to reschedule if needed, and wish them well, and politely say goodbye."
        )
    )


@agent.on_action_request
def on_action_request(call: guava.Call, intent_summary: str):
    return _mid_call_intent.classify(intent_summary)


@agent.on_action("do_not_contact")
def handle_dnc(call: guava.Call) -> None:
    logging.info("Client %s requested DNC mid-call.", call.get_variable("contact_name"))
    call.hangup(
        final_instructions=(
            "Acknowledge their request. Let them know they have been removed from "
            "the contact list and will not be called again, and wish them well, and politely say goodbye."
        )
    )


@agent.on_action("speak_to_someone")
def handle_transfer(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            "Let them know their attorney or a staff member will call them back "
            "within one business day. Ask if there's a preferred time and thank them, and politely say goodbye."
        )
    )


@agent.on_outbound_failed
def on_outbound_failed(event: OutboundCallFailed) -> None:
    logging.error("Outbound call failed: %s (code %d)", event.error_reason, event.error_code)


@agent.on_session_end
def on_session_end(call: guava.Call, event: BotSessionEnded) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "use_case": "legal_scheduling",
        "contact_name": call.get_variable("contact_name"),
        "client_id": call.get_variable("client_id"),
        "attorney": call.get_variable("attorney"),
        "matter_number": call.get_variable("matter_number"),
        "appointment_id": call.get_variable("appointment_id"),
        "identity_verified": call.get_field("dob") is not None,
        "selected_slot": call.get_field("selected_slot"),
        "meeting_format": call.get_field("meeting_format"),
        "confirmation_email": call.get_field("confirmation_email"),
        "special_accommodations": call.get_field("special_accommodations"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound scheduling call for Hargrove & Associates"
    )
    parser.add_argument("phone", help="Phone number to dial")
    parser.add_argument("--name", required=True, help="Full name of the client")
    parser.add_argument(
        "--client-id",
        required=True,
        help="Client ID (try CLT-5001, CLT-5002, or CLT-5003)",
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
            "contact_name": args.name,
            "client_id": args.client_id,
        },
    )

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
# Mock API — simulates appointment and scheduling backend
# ---------------------------------------------------------------------------

MOCK_APPOINTMENTS = {
    "APT-10231": {
        "patient": "Linda Chen",
        "dob": "1979-04-18",
        "provider": "Dr. Patel",
        "date": "2026-08-04",
        "time": "10:00 AM",
        "type": "Dental Cleaning",
    },
    "APT-10232": {
        "patient": "Marcus Johnson",
        "dob": "1991-11-02",
        "provider": "Dr. Rivera",
        "date": "2026-08-05",
        "time": "2:30 PM",
        "type": "Crown Preparation",
    },
    "APT-10233": {
        "patient": "Sarah Kim",
        "dob": "1985-06-27",
        "provider": "Dr. Patel",
        "date": "2026-08-06",
        "time": "9:00 AM",
        "type": "Root Canal Follow-Up",
    },
}

MOCK_AVAILABLE_SLOTS = [
    {"date": "2026-08-07", "time": "9:00 AM", "provider": "Dr. Patel"},
    {"date": "2026-08-07", "time": "2:00 PM", "provider": "Dr. Rivera"},
    {"date": "2026-08-08", "time": "10:30 AM", "provider": "Dr. Patel"},
    {"date": "2026-08-08", "time": "3:00 PM", "provider": "Dr. Rivera"},
    {"date": "2026-08-11", "time": "11:00 AM", "provider": "Dr. Patel"},
]


def _slot_to_iso(slot: dict) -> str:
    return datetime.strptime(f"{slot['date']} {slot['time']}", "%Y-%m-%d %I:%M %p").isoformat()


_SLOTS_BY_ISO = {_slot_to_iso(slot): slot for slot in MOCK_AVAILABLE_SLOTS}

datetime_filter = DatetimeFilter(source_list=list(_SLOTS_BY_ISO.keys()))


def lookup_appointment(appointment_id):
    return MOCK_APPOINTMENTS.get(appointment_id)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

agent = guava.Agent(
    name="Taylor",
    organization="Bright Smile Dental",
    purpose=(
        "remind patients of upcoming appointments, confirm attendance, and "
        "assist with rescheduling by offering available time slots"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
    "speak_to_someone": "The caller wants to speak to the front desk or a real person",
})


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(
        contact_full_name=call.get_variable("patient_name"),
        voicemail_message=(
            f"Hi, this is Taylor from Bright Smile Dental calling for "
            f"{call.get_variable('patient_name')}. We're reaching out about an "
            f"upcoming appointment. Please call us back at 555-0140 at your "
            f"convenience. Thank you!"
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    patient_name = call.get_variable("patient_name")

    if outcome == "available":
        call.set_task(
            "verify_patient",
            objective=(
                f"Verify the identity of {patient_name} before discussing any "
                f"appointment details. Ask for their date of birth. Do not share "
                f"appointment specifics until identity is confirmed."
            ),
            checklist=[
                guava.Say(
                    "I'm calling about an upcoming appointment. Before I share "
                    "any details, I just need to quickly verify your identity."
                ),
                guava.Field(
                    key="dob",
                    description="The patient's date of birth for identity verification",
                    field_type="text",
                    required=True,
                ),
            ],
        )
    elif outcome == "do_not_contact":
        logging.info("Patient %s requested no further contact.", patient_name)
        call.hangup(
            final_instructions=(
                "Acknowledge their request. Let them know they will not be "
                "contacted again and have been removed from the call list, and politely say goodbye."
            )
        )
    elif outcome == "wrong_number":
        logging.info("Wrong number reached for %s.", patient_name)
        call.hangup(final_instructions="Apologize for the mistake and wish them well, and politely say goodbye.")
    else:
        logging.info("Could not reach %s (outcome: %s).", patient_name, outcome)
        call.hangup()


@agent.on_task_complete("verify_patient")
def on_patient_verified(call: guava.Call) -> None:
    appointment_id = call.get_variable("appointment_id")
    dob = call.get_field("dob")
    appointment = lookup_appointment(appointment_id)

    if appointment is None or appointment["dob"] != dob:
        logging.warning("Identity verification failed for appointment %s.", appointment_id)
        call.hangup(
            final_instructions=(
                "Let them know the date of birth provided does not match our "
                "records. For their privacy, you cannot share appointment details. "
                "Suggest they call the office directly at 555-0140, and politely say goodbye."
            )
        )
        return

    patient_name = call.get_variable("patient_name")

    call.add_info("appointment_details", {
        "appointment_id": appointment_id,
        "date": appointment["date"],
        "time": appointment["time"],
        "type": appointment["type"],
    })

    call.set_task(
        "confirm_appointment",
        objective=(
            f"Confirm the upcoming appointment with {patient_name}. Their "
            f"appointment is on {appointment['date']} at {appointment['time']} "
            f"for a {appointment['type']}. Ask if they can make it or need to "
            f"reschedule. Do not mention the provider's name or any clinical "
            f"details beyond the appointment type already shared."
        ),
        checklist=[
            guava.Say(
                f"Great, thank you {patient_name}. You have an appointment on "
                f"{appointment['date']} at {appointment['time']} for a "
                f"{appointment['type']}. Does that still work for you?"
            ),
            guava.Field(
                key="appointment_confirmed",
                description="Whether the patient confirms the appointment or needs to reschedule",
                field_type="multiple_choice",
                choices=["confirm", "reschedule"],
                required=True,
            ),
        ],
    )


@agent.on_task_complete("confirm_appointment")
def on_confirm_done(call: guava.Call) -> None:
    confirmed = call.get_field("appointment_confirmed")
    patient_name = call.get_variable("patient_name")

    if confirmed == "reschedule":
        call.set_task(
            "reschedule",
            objective=(
                f"{patient_name} needs to reschedule. Ask for their preferred "
                f"day and time, then present the best available options from the "
                f"scheduling system."
            ),
            checklist=[
                guava.Field(
                    key="preferred_time",
                    description=(
                        "The patient's preferred day and time for their rescheduled "
                        "appointment. Ask what days and times generally work best."
                    ),
                    field_type="text",
                    required=True,
                    searchable=True,
                ),
            ],
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {patient_name} for confirming. Remind them to arrive 10 "
                f"minutes early to complete any necessary paperwork. Wish them a "
                f"great day, and politely say goodbye."
            )
        )


@agent.on_search_query("preferred_time")
def on_search_preferred_time(call: guava.Call, query: str):
    matching, fallback = datetime_filter.filter(query, max_results=3)

    def describe(iso: str) -> str:
        slot = _SLOTS_BY_ISO[iso]
        return f"{slot['date']} at {slot['time']} with {slot['provider']}"

    return [describe(iso) for iso in matching], [describe(iso) for iso in fallback]


@agent.on_task_complete("reschedule")
def on_reschedule_done(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")
    preferred_time = call.get_field("preferred_time")

    logging.info("Reschedule requested by %s — preferred: %s", patient_name, preferred_time)
    call.hangup(
        final_instructions=(
            f"Let {patient_name} know the new appointment time has been noted "
            f"and a confirmation will be sent. Remind them to arrive 10 minutes "
            f"early. Thank them and wish them a great day, and politely say goodbye."
        )
    )


@agent.on_action_request
def on_action_request(call: guava.Call, intent_summary: str):
    return _mid_call_intent.classify(intent_summary)


@agent.on_action("do_not_contact")
def handle_dnc(call: guava.Call) -> None:
    logging.info("Patient %s requested DNC mid-call.", call.get_variable("patient_name"))
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
            "Let them know the front desk team at Bright Smile Dental will call "
            "them back within one business day. Ask if there is a preferred time "
            "and thank them for their patience, and politely say goodbye."
        )
    )


@agent.on_outbound_failed
def on_outbound_failed(event: OutboundCallFailed) -> None:
    logging.error("Outbound call failed: %s (code %d)", event.error_reason, event.error_code)


@agent.on_session_end
def on_session_end(call: guava.Call, event: BotSessionEnded) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "use_case": "appointment_reminder",
        "patient_name": call.get_variable("patient_name"),
        "appointment_id": call.get_variable("appointment_id"),
        "dob_verified": call.get_field("dob") is not None,
        "appointment_confirmed": call.get_field("appointment_confirmed"),
        "preferred_time": call.get_field("preferred_time"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound appointment reminder call for Bright Smile Dental"
    )
    parser.add_argument("phone", help="Patient phone number to call")
    parser.add_argument("--name", required=True, help="Full name of the patient")
    parser.add_argument(
        "--appointment-id",
        required=True,
        help="Appointment ID (try APT-10231, APT-10232, or APT-10233)",
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
            "patient_name": args.name,
            "appointment_id": args.appointment_id,
        },
    )

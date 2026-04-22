import json
import logging
import os
from datetime import datetime, timezone

import guava
import requests
from guava import logging_utils

FHIR_BASE_URL = os.environ["MEDITECH_FHIR_BASE_URL"]


def get_headers() -> dict:
    return {
        "Authorization": f"Bearer {os.environ['MEDITECH_ACCESS_TOKEN']}",
        "Content-Type": "application/json",
        "Accept": "application/fhir+json",
    }


agent = guava.Agent(
    name="Casey",
    organization="Valley General Hospital",
    purpose=(
        "to help patients schedule hospital appointments and procedures by finding "
        "available times and booking them directly into the scheduling system"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "collect_scheduling_preferences",
        objective=(
            "A patient has called Valley General Hospital to schedule an appointment or "
            "procedure. Greet them, collect their identifying information and scheduling "
            "preferences, and find an available time that works for them."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling Valley General Hospital scheduling. My name is Casey "
                "and I'd be happy to help you book an appointment today."
            ),
            guava.Field(
                key="first_name",
                description="Ask the caller for their first name.",
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="last_name",
                description="Ask the caller for their last name.",
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="date_of_birth",
                description=(
                    "Ask for the patient's date of birth so we can pull up their record. "
                    "Capture in YYYY-MM-DD format (e.g. 1985-03-15)."
                ),
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="appointment_type",
                description=(
                    "Ask what type of appointment or procedure they need. Options are: "
                    "primary care visit, specialist consult, outpatient procedure, radiology, "
                    "or lab work. Capture their choice exactly."
                ),
                field_type="multiple_choice",
                choices=[
                    "primary care visit",
                    "specialist consult",
                    "outpatient procedure",
                    "radiology",
                    "lab work",
                ],
                required=True,
            ),
            guava.Field(
                key="preferred_date",
                description=(
                    "Ask what date they would prefer for their appointment. "
                    "Capture in YYYY-MM-DD format (e.g. 2026-04-15)."
                ),
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="time_of_day_preference",
                description=(
                    "Ask whether they prefer a morning appointment, an afternoon appointment, "
                    "or if they have no preference. Capture 'morning', 'afternoon', or 'no preference'."
                ),
                field_type="multiple_choice",
                choices=["morning", "afternoon", "no preference"],
                required=True,
            ),
        ],
    )


@agent.on_task_complete("collect_scheduling_preferences")
def search_availability(call: guava.Call) -> None:
    first_name = call.get_field("first_name")
    last_name = call.get_field("last_name")
    dob = call.get_field("date_of_birth")
    appointment_type = call.get_field("appointment_type")
    preferred_date = call.get_field("preferred_date")
    time_preference = call.get_field("time_of_day_preference")

    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": "Casey",
        "organization": "Valley General Hospital",
        "use_case": "appointment_scheduling",
        "phase": "preferences_collected",
        "fields": {
            "first_name": first_name,
            "last_name": last_name,
            "date_of_birth": dob,
            "appointment_type": appointment_type,
            "preferred_date": preferred_date,
            "time_of_day_preference": time_preference,
        },
    }
    print(json.dumps(results, indent=2))
    logging.info("Scheduling preferences collected for %s %s.", first_name, last_name)

    patient_fhir_id = None
    selected_slot = None

    try:
        # Step 1: Look up the patient in Meditech by last name + DOB to get their FHIR ID.
        # We need this to link the booked appointment to the correct patient record.
        patient_resp = requests.get(
            f"{FHIR_BASE_URL}/Patient",
            headers=get_headers(),
            params={"family": last_name, "birthdate": dob},
            timeout=10,
        )
        patient_resp.raise_for_status()
        patient_entries = patient_resp.json().get("entry", [])
        if patient_entries:
            patient_fhir_id = patient_entries[0]["resource"]["id"]
            logging.info("Found patient in Meditech: %s", patient_fhir_id)
        else:
            logging.warning(
                "No matching patient found in Meditech for %s %s (DOB: %s).",
                first_name, last_name, dob,
            )

        # Step 2: Search for free slots on or after the preferred date.
        # Return up to 5 and take the first so we can present a concrete option.
        slot_resp = requests.get(
            f"{FHIR_BASE_URL}/Slot",
            headers=get_headers(),
            params={
                "start": f"ge{preferred_date}",
                "status": "free",
                "_count": "5",
            },
            timeout=10,
        )
        slot_resp.raise_for_status()
        slot_entries = slot_resp.json().get("entry", [])

        if slot_entries:
            # Filter by time-of-day preference when possible.
            selected = None
            for entry in slot_entries:
                slot = entry["resource"]
                slot_start = slot.get("start", "")
                try:
                    dt = datetime.fromisoformat(slot_start.replace("Z", "+00:00"))
                    hour = dt.hour
                    if time_preference == "morning" and hour < 12:
                        selected = slot
                        break
                    elif time_preference == "afternoon" and hour >= 12:
                        selected = slot
                        break
                except (ValueError, AttributeError):
                    pass

            # Fall back to the first slot if no preference-matched slot was found.
            if selected is None:
                selected = slot_entries[0]["resource"]

            selected_slot = selected
            slot_start = selected_slot.get("start", "")
            slot_id = selected_slot.get("id", "")
            logging.info(
                "Found available slot: %s (start: %s)", slot_id, slot_start
            )

            try:
                dt = datetime.fromisoformat(slot_start.replace("Z", "+00:00"))
                display_time = dt.strftime("%A, %B %-d at %-I:%M %p")
            except (ValueError, AttributeError):
                display_time = slot_start

            call.set_variable("patient_fhir_id", patient_fhir_id)
            call.set_variable("selected_slot", selected_slot)

            call.set_task(
                "confirm_booking",
                objective=(
                    f"An available {appointment_type} slot has been found for {first_name}. "
                    "Present the time and confirm whether it works for them."
                ),
                checklist=[
                    guava.Say(
                        f"Great news — I found an opening for a {appointment_type} on "
                        f"{display_time}. Would that time work for you?"
                    ),
                    guava.Field(
                        key="booking_confirmed",
                        description=(
                            "Confirm whether the patient accepts the proposed appointment time. "
                            "Capture 'yes' if they accept or 'no' if they decline."
                        ),
                        field_type="multiple_choice",
                        choices=["yes", "no"],
                        required=True,
                    ),
                ],
            )
            return

        logging.info("No available slots found matching preferences.")
    except Exception as e:
        logging.error("Failed to search Meditech for availability: %s", e)

    call.hangup(
        final_instructions=(
            f"Apologize to {first_name} and let them know we were not able to find an "
            "open slot matching their preferences right now. Assure them that a scheduling "
            "coordinator from Valley General Hospital will call them back within one "
            "business day to find a time that works. Thank them for calling."
        )
    )


@agent.on_task_complete("confirm_booking")
def finalize_booking(call: guava.Call) -> None:
    confirmed = call.get_field("booking_confirmed")
    first_name = call.get_field("first_name")
    last_name = call.get_field("last_name")
    appointment_type = call.get_field("appointment_type")
    patient_fhir_id = call.get_variable("patient_fhir_id")
    selected_slot = call.get_variable("selected_slot")

    if not confirmed or confirmed.strip().lower() != "yes":
        call.hangup(
            final_instructions=(
                f"Acknowledge that the offered time doesn't work for {first_name}. "
                "Let them know a scheduling coordinator from Valley General Hospital will "
                "call them back with additional options within one business day. "
                "Thank them for calling."
            )
        )
        return

    slot_id = selected_slot.get("id", "")
    slot_start = selected_slot.get("start", "")
    slot_end = selected_slot.get("end", "")

    # Patient confirmed the slot — POST a new Appointment resource to Meditech Expanse.
    # Link the slot reference and patient FHIR ID (or display name if lookup failed).
    try:
        participant = []
        if patient_fhir_id:
            participant.append({
                "actor": {"reference": f"Patient/{patient_fhir_id}"},
                "status": "accepted",
            })
        else:
            participant.append({
                "actor": {"display": f"{first_name} {last_name}"},
                "status": "accepted",
            })

        appt_payload = {
            "resourceType": "Appointment",
            "status": "booked",
            "serviceType": [{"text": appointment_type}],
            "start": slot_start,
            "end": slot_end,
            "slot": [{"reference": f"Slot/{slot_id}"}],
            "participant": participant,
            "comment": f"Booked via inbound phone call — {first_name} {last_name}",
        }

        resp = requests.post(
            f"{FHIR_BASE_URL}/Appointment",
            headers=get_headers(),
            json=appt_payload,
            timeout=10,
        )
        resp.raise_for_status()
        appt_id = resp.json().get("id", "")
        logging.info("Meditech Appointment booked: %s", appt_id)
    except Exception as e:
        logging.error("Failed to book Meditech Appointment: %s", e)

    booking_results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": "Casey",
        "organization": "Valley General Hospital",
        "use_case": "appointment_scheduling",
        "phase": "booked",
        "patient_fhir_id": patient_fhir_id,
        "slot_id": slot_id,
        "appointment_start": slot_start,
        "appointment_end": slot_end,
        "fields": {
            "first_name": first_name,
            "last_name": last_name,
            "appointment_type": appointment_type,
            "booking_confirmed": confirmed,
        },
    }
    print(json.dumps(booking_results, indent=2))
    logging.info("Appointment booking results saved locally.")

    try:
        dt = datetime.fromisoformat(slot_start.replace("Z", "+00:00"))
        display_time = dt.strftime("%A, %B %-d at %-I:%M %p")
    except (ValueError, AttributeError):
        display_time = slot_start

    call.hangup(
        final_instructions=(
            f"Confirm to {first_name} that their {appointment_type} appointment has been "
            f"booked for {display_time} at Valley General Hospital. Remind them to arrive "
            "15 minutes early and to bring their insurance card and a valid photo ID. "
            "Let them know they will receive a confirmation by phone or email. "
            "Thank them for calling and wish them a great day."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])

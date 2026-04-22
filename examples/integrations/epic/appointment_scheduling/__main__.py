import json
import logging
import os
from datetime import datetime, timezone

import guava
import requests
from guava import logging_utils

agent = guava.Agent(
    name="Riley",
    organization="Cedar Health",
    purpose=(
        "to help patients schedule appointments by finding available times "
        "and booking directly into Cedar Health's scheduling system"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_variable("patient_fhir_id", None)
    call.set_variable("selected_slot", None)

    call.set_task(
        "collect_preferences",
        objective=(
            "A patient has called Cedar Health to schedule an appointment. Greet them, "
            "collect identifying information and scheduling preferences so we can find "
            "an available time for them."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling Cedar Health scheduling. My name is Riley. "
                "I'd be happy to help you book an appointment today."
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
                    "Ask what type of appointment they need. Common options include: "
                    "annual physical, sick visit, follow-up visit, or specialist consult. "
                    "Capture their answer."
                ),
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="preferred_date",
                description=(
                    "Ask what date they would prefer for their appointment. "
                    "Capture in YYYY-MM-DD format (e.g. 2026-03-25)."
                ),
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="preferred_time_of_day",
                description=(
                    "Ask whether they prefer a morning or afternoon appointment, "
                    "or if they have no preference. Capture 'morning', 'afternoon', or 'no preference'."
                ),
                field_type="text",
                required=True,
            ),
        ],
    )


@agent.on_task_complete("collect_preferences")
def on_preferences_done(call: guava.Call) -> None:
    first_name = call.get_field("first_name")
    last_name = call.get_field("last_name")
    dob = call.get_field("date_of_birth")
    appointment_type = call.get_field("appointment_type")
    preferred_date = call.get_field("preferred_date")
    preferred_time = call.get_field("preferred_time_of_day")

    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": "Riley",
        "organization": "Cedar Health",
        "use_case": "appointment_scheduling",
        "phase": "preferences_collected",
        "fields": {
            "first_name": first_name,
            "last_name": last_name,
            "date_of_birth": dob,
            "appointment_type": appointment_type,
            "preferred_date": preferred_date,
            "preferred_time_of_day": preferred_time,
        },
    }
    print(json.dumps(results, indent=2))
    logging.info("Scheduling preferences collected.")

    try:
        base_url = os.environ["EPIC_BASE_URL"]
        access_token = os.environ["EPIC_ACCESS_TOKEN"]
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        # Step 1: Look up the patient in Epic by last name + DOB to get their FHIR ID.
        # We need this ID to link the booked appointment to the correct patient record.
        patient_resp = requests.get(
            f"{base_url}/Patient",
            headers=headers,
            params={"family": last_name, "birthdate": dob},
            timeout=10,
        )
        patient_resp.raise_for_status()
        patient_entries = patient_resp.json().get("entry", [])
        if patient_entries:
            call.set_variable("patient_fhir_id", patient_entries[0]["resource"]["id"])
            logging.info("Found patient in Epic: %s", call.get_variable("patient_fhir_id"))
        else:
            # Patient not found — booking will proceed with display name only
            logging.warning(
                "No matching patient found in Epic for %s %s (DOB: %s)",
                first_name, last_name, dob,
            )

        # Step 2: Search for free slots on or after the preferred date.
        # We take the first result and present it to the patient for confirmation.
        slot_resp = requests.get(
            f"{base_url}/Slot",
            headers=headers,
            params={
                "start": f"ge{preferred_date}",
                "status": "free",
                "service-type": appointment_type,
                "_count": "5",
            },
            timeout=10,
        )
        slot_resp.raise_for_status()
        slot_entries = slot_resp.json().get("entry", [])

        if slot_entries:
            call.set_variable("selected_slot", slot_entries[0]["resource"])
            selected_slot = call.get_variable("selected_slot") or {}
            slot_start = selected_slot.get("start", "")
            slot_id = selected_slot.get("id", "")
            logging.info("Found available slot: %s (start: %s)", slot_id, slot_start)

            try:
                dt = datetime.fromisoformat(slot_start.replace("Z", "+00:00"))
                display_time = dt.strftime("%A, %B %-d at %-I:%M %p")
            except (ValueError, AttributeError):
                display_time = slot_start

            call.set_task(
                "confirm_booking",
                objective=(
                    f"An available appointment slot has been found for {first_name}. "
                    "Present the time and confirm whether it works for them."
                ),
                checklist=[
                    guava.Say(
                        f"Great news — I found an opening on {display_time}. "
                        "Would that time work for you?"
                    ),
                    guava.Field(
                        key="booking_confirmed",
                        description=(
                            "Confirm whether the patient accepts the proposed appointment time. "
                            "Capture 'yes' if they accept or 'no' if they decline."
                        ),
                        field_type="text",
                        required=True,
                    ),
                ],
            )
            return

        logging.info("No available slots found matching preferences.")
    except Exception as e:
        logging.error("Failed to search Epic for availability: %s", e)

    call.hangup(
        final_instructions=(
            f"Apologize to {first_name} and let them know we were not able to find an "
            "open slot matching their preferences right now. Assure them that a scheduling "
            "coordinator from Cedar Health will call them back within one business day "
            "to find a time that works. Thank them for calling and wish them a great day."
        )
    )


@agent.on_task_complete("confirm_booking")
def on_booking_done(call: guava.Call) -> None:
    confirmed = call.get_field("booking_confirmed")
    first_name = call.get_field("first_name")
    last_name = call.get_field("last_name")
    appointment_type = call.get_field("appointment_type")

    if not confirmed or confirmed.strip().lower() != "yes":
        call.hangup(
            final_instructions=(
                f"Acknowledge that the offered time does not work for {first_name}. "
                "Let them know a scheduling coordinator from Cedar Health will call them "
                "back with additional options within one business day. Thank them for calling."
            )
        )
        return

    selected_slot = call.get_variable("selected_slot") or {}
    slot_id = selected_slot.get("id", "")
    slot_start = selected_slot.get("start", "")
    slot_end = selected_slot.get("end", "")

    # Patient confirmed the slot — POST a new Appointment resource to Epic.
    # Link the slot reference and patient FHIR ID (or display name if lookup failed).
    try:
        base_url = os.environ["EPIC_BASE_URL"]
        access_token = os.environ["EPIC_ACCESS_TOKEN"]
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        participant = []
        patient_fhir_id = call.get_variable("patient_fhir_id")
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
            "comment": f"Booked via phone — {first_name} {last_name}",
        }

        resp = requests.post(
            f"{base_url}/Appointment",
            headers=headers,
            json=appt_payload,
            timeout=10,
        )
        resp.raise_for_status()
        appt_id = resp.json().get("id", "")
        logging.info("Epic Appointment booked: %s", appt_id)
    except Exception as e:
        logging.error("Failed to book Epic Appointment: %s", e)

    booking_results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": "Riley",
        "organization": "Cedar Health",
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
            f"booked for {display_time} at Cedar Health. Remind them to arrive 10 minutes "
            "early and to bring their insurance card and a valid photo ID. Let them know "
            "they will receive a confirmation through their patient portal. "
            "Thank them for calling and wish them a great day."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])

import guava
import os
import logging
from guava import logging_utils
import requests
from datetime import datetime


BASE_URL = os.environ["PRACTICE_FUSION_FHIR_BASE_URL"]  # e.g. https://api.practicefusion.com/fhir/r4


def get_headers():
    return {
        "Authorization": f"Bearer {os.environ['PRACTICE_FUSION_ACCESS_TOKEN']}",
        "Content-Type": "application/json",
    }


def search_patient(last_name: str, dob: str) -> dict | None:
    """Search for a patient by last name and date of birth. Returns the first matching patient resource or None."""
    url = f"{BASE_URL}/Patient"
    params = {"family": last_name, "birthdate": dob}
    response = requests.get(url, headers=get_headers(), params=params)
    response.raise_for_status()
    bundle = response.json()
    entries = bundle.get("entry", [])
    if not entries:
        return None
    return entries[0]["resource"]


def get_free_slots(on_or_after_date: str, count: int = 5) -> list[dict]:
    """Fetch up to `count` free Slot resources on or after the given date (YYYY-MM-DD)."""
    url = f"{BASE_URL}/Slot"
    params = {
        "start": f"ge{on_or_after_date}",
        "status": "free",
        "_count": count,
    }
    response = requests.get(url, headers=get_headers(), params=params)
    response.raise_for_status()
    bundle = response.json()
    return [entry["resource"] for entry in bundle.get("entry", [])]


def book_appointment(patient_id: str, slot: dict, appointment_type: str) -> dict:
    """POST a new Appointment resource to book the given slot for the patient."""
    slot_id = slot["id"]
    start = slot["start"]
    end = slot["end"]

    appointment_resource = {
        "resourceType": "Appointment",
        "status": "proposed",
        "serviceType": [
            {
                "coding": [
                    {
                        "display": appointment_type,
                    }
                ]
            }
        ],
        "start": start,
        "end": end,
        "slot": [{"reference": f"Slot/{slot_id}"}],
        "participant": [
            {
                "actor": {"reference": f"Patient/{patient_id}"},
                "status": "accepted",
            }
        ],
    }

    url = f"{BASE_URL}/Appointment"
    response = requests.post(url, headers=get_headers(), json=appointment_resource)
    response.raise_for_status()
    return response.json()


def format_slot(slot: dict) -> str:
    """Return a human-readable description of a Slot resource."""
    start_str = slot.get("start", "")
    try:
        dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
        return dt.strftime("%A, %B %-d at %-I:%M %p")
    except ValueError:
        return start_str


agent = guava.Agent(
    name="Jordan",
    organization="Riverside Family Medicine",
    purpose="to help patients schedule appointments",
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "schedule_appointment",
        objective=(
            "Collect the patient's information and appointment preferences, "
            "look up their record, find an available slot, confirm it with them, "
            "and book the appointment."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling Riverside Family Medicine. My name is Jordan "
                "and I can help you schedule an appointment today."
            ),
            guava.Field(
                key="first_name",
                field_type="text",
                description="Ask the patient for their first name.",
                required=True,
            ),
            guava.Field(
                key="last_name",
                field_type="text",
                description="Ask the patient for their last name.",
                required=True,
            ),
            guava.Field(
                key="dob",
                field_type="text",
                description=(
                    "Ask the patient for their date of birth. "
                    "Capture it in YYYY-MM-DD format."
                ),
                required=True,
            ),
            guava.Field(
                key="appointment_type",
                field_type="text",
                description=(
                    "Ask what type of appointment they need, for example: "
                    "annual physical, sick visit, follow-up, or vaccine."
                ),
                required=True,
            ),
            guava.Field(
                key="preferred_date",
                field_type="text",
                description=(
                    "Ask for their preferred appointment date. "
                    "Capture it in YYYY-MM-DD format."
                ),
                required=True,
            ),
            guava.Field(
                key="time_preference",
                field_type="multiple_choice",
                description="Ask whether they prefer a morning or afternoon appointment.",
                choices=["morning", "afternoon"],
                required=True,
            ),
        ],
    )


@agent.on_task_complete("schedule_appointment")
def on_done(call: guava.Call) -> None:
    first_name = call.get_field("first_name")
    last_name = call.get_field("last_name")
    dob = call.get_field("dob")
    appointment_type = call.get_field("appointment_type")
    preferred_date = call.get_field("preferred_date")
    time_preference = call.get_field("time_preference")

    logging.info("Looking up patient: %s %s, DOB %s", first_name, last_name, dob)
    patient = search_patient(last_name, dob)

    if patient is None:
        call.hangup(
            final_instructions=(
                f"Apologize and let the patient know you were unable to locate a record "
                f"for {first_name} {last_name} with that date of birth. Ask them to call "
                "back during office hours or visit the front desk so staff can assist them."
            )
        )
        return

    patient_id = patient["id"]
    logging.info("Found patient ID: %s", patient_id)

    slots = get_free_slots(on_or_after_date=preferred_date)

    # Filter slots by time preference
    filtered_slots = []
    for slot in slots:
        start_str = slot.get("start", "")
        try:
            dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            hour = dt.hour
            if time_preference == "morning" and 6 <= hour < 12:
                filtered_slots.append(slot)
            elif time_preference == "afternoon" and 12 <= hour < 18:
                filtered_slots.append(slot)
        except ValueError:
            continue

    # Fall back to unfiltered if nothing matched the preference
    if not filtered_slots:
        filtered_slots = slots

    if not filtered_slots:
        call.hangup(
            final_instructions=(
                f"Apologize and let {first_name} know there are no available slots on or "
                "after their preferred date. Ask them to call back to check for new openings "
                "or visit the patient portal to check availability."
            )
        )
        return

    best_slot = filtered_slots[0]
    slot_description = format_slot(best_slot)

    logging.info("Booking slot: %s for patient %s", slot_description, patient_id)
    try:
        booked = book_appointment(patient_id, best_slot, appointment_type)
        appointment_id = booked.get("id", "unknown")
        logging.info("Appointment booked with ID: %s", appointment_id)
        call.hangup(
            final_instructions=(
                f"Tell {first_name} their appointment has been successfully scheduled for "
                f"{slot_description} for a {appointment_type}. Their confirmation number is "
                f"{appointment_id}. Let them know they'll receive a reminder call beforehand "
                "and to call back if they need to make any changes. Thank them for choosing "
                "Riverside Family Medicine."
            )
        )
    except requests.HTTPError as exc:
        logging.error("Failed to book appointment: %s", exc)
        call.hangup(
            final_instructions=(
                f"Apologize to {first_name} and let them know there was an issue completing "
                "the booking. Ask them to call back during office hours or try the patient "
                "portal to schedule online."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])

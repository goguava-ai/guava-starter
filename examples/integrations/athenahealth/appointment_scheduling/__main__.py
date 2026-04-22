import json
import logging
import os

import guava
import requests
from guava import logging_utils

PRACTICE_ID = os.environ["ATHENA_PRACTICE_ID"]
BASE_URL = f"https://api.platform.athenahealth.com/v1/{PRACTICE_ID}"


def get_access_token() -> str:
    resp = requests.post(
        "https://api.platform.athenahealth.com/oauth2/v1/token",
        data={"grant_type": "client_credentials"},
        auth=(os.environ["ATHENA_CLIENT_ID"], os.environ["ATHENA_CLIENT_SECRET"]),
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def search_patients(last_name: str, dob: str, headers: dict) -> list:
    """Search for patients by last name and date of birth."""
    resp = requests.get(
        f"{BASE_URL}/patients",
        headers=headers,
        params={"lastname": last_name, "dob": dob},
        timeout=10,
    )
    if not resp.ok:
        return []
    return resp.json().get("patients", [])


def get_open_appointments(appointment_type_id: str, start_date: str, headers: dict) -> list:
    """Fetch open (available) appointment slots."""
    resp = requests.get(
        f"{BASE_URL}/appointments/open",
        headers=headers,
        params={
            "appointmenttypeid": appointment_type_id,
            "startdate": start_date,
            "limit": 5,
        },
        timeout=10,
    )
    if not resp.ok:
        return []
    return resp.json().get("appointments", [])


def book_appointment(appointment_id: str, patient_id: str, notes: str, headers: dict) -> bool:
    """Books an open appointment slot for the given patient."""
    resp = requests.put(
        f"{BASE_URL}/appointments/{appointment_id}",
        headers={**headers, "Content-Type": "application/x-www-form-urlencoded"},
        data={
            "patientid": patient_id,
            "appointmentstatus": "f",  # 'f' = future/booked
            "appointmentnote": notes,
        },
        timeout=10,
    )
    return resp.ok


agent = guava.Agent(
    name="Avery",
    organization="Maple Medical Group",
    purpose=(
        "to help patients schedule appointments at Maple Medical Group"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    headers = {}
    try:
        token = get_access_token()
        headers = {"Authorization": f"Bearer {token}"}
    except Exception as e:
        logging.error("Failed to get Athenahealth token at startup: %s", e)

    call.set_variable("headers", headers)
    call.set_variable("patient_id", None)
    call.set_variable("selected_appointment", None)

    call.set_task(
        "collect_scheduling_preferences",
        objective=(
            "A patient has called Maple Medical Group to schedule an appointment. "
            "Collect their information and scheduling preferences."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling Maple Medical Group scheduling. "
                "My name is Avery. I'd be happy to help you book an appointment today."
            ),
            guava.Field(
                key="first_name",
                field_type="text",
                description="Ask for the caller's first name.",
                required=True,
            ),
            guava.Field(
                key="last_name",
                field_type="text",
                description="Ask for the caller's last name.",
                required=True,
            ),
            guava.Field(
                key="date_of_birth",
                field_type="text",
                description=(
                    "Ask for their date of birth so we can pull up their record. "
                    "Capture in MM/DD/YYYY format."
                ),
                required=True,
            ),
            guava.Field(
                key="reason_for_visit",
                field_type="text",
                description=(
                    "Ask what brings them in. Common reasons: annual physical, sick visit, "
                    "follow-up, specialist consult, new patient visit."
                ),
                required=True,
            ),
            guava.Field(
                key="preferred_date",
                field_type="text",
                description=(
                    "Ask what date they prefer. Capture in MM/DD/YYYY format."
                ),
                required=True,
            ),
            guava.Field(
                key="preferred_time",
                field_type="multiple_choice",
                description="Ask whether they prefer morning, afternoon, or have no preference.",
                choices=["morning", "afternoon", "no preference"],
                required=True,
            ),
        ],
    )


@agent.on_task_complete("collect_scheduling_preferences")
def on_preferences_collected(call: guava.Call) -> None:
    first_name = call.get_field("first_name")
    last_name = call.get_field("last_name")
    dob = call.get_field("date_of_birth")
    reason = call.get_field("reason_for_visit")
    preferred_date = call.get_field("preferred_date")
    preferred_time = call.get_field("preferred_time")

    logging.info("Scheduling request: %s %s, DOB %s, reason: %s", first_name, last_name, dob, reason)

    headers = call.get_variable("headers") or {}

    # Look up patient in Athenahealth
    patient_id = None
    try:
        patients = search_patients(last_name, dob, headers)
        if patients:
            patient_id = patients[0].get("patientid")
            logging.info("Found patient in Athenahealth: %s", patient_id)
        else:
            logging.warning("No patient found for %s %s (DOB: %s)", first_name, last_name, dob)
    except Exception as e:
        logging.error("Patient search failed: %s", e)

    # Search for open appointment slots
    # Use a generic appointment type ID; in production this would map to the reason for visit
    appointment_type_id = os.environ.get("ATHENA_APPOINTMENT_TYPE_ID", "1")

    open_slots = []
    try:
        # Convert preferred_date from MM/DD/YYYY to MM/DD/YYYY (Athenahealth format)
        open_slots = get_open_appointments(appointment_type_id, preferred_date, headers)
    except Exception as e:
        logging.error("Open appointment search failed: %s", e)

    if open_slots:
        selected_appointment = open_slots[0]
        appt_id = selected_appointment.get("appointmentid", "")
        appt_date = selected_appointment.get("date", "")
        appt_time = selected_appointment.get("starttime", "")
        provider = selected_appointment.get("providername", "a provider")

        display_time = f"{appt_date} at {appt_time} with {provider}"

        call.set_variable("headers", headers)
        call.set_variable("patient_id", patient_id)
        call.set_variable("selected_appointment", selected_appointment)
        call.set_variable("appt_id", appt_id)
        call.set_variable("display_time", display_time)

        call.set_task(
            "confirm_appointment_booking",
            objective=(
                f"An available slot has been found for {first_name}. "
                "Present the time and confirm whether it works."
            ),
            checklist=[
                guava.Say(
                    f"Great news — I found an opening on {display_time}. "
                    "Would that time work for you?"
                ),
                guava.Field(
                    key="booking_confirmed",
                    field_type="multiple_choice",
                    description="Ask if the patient accepts the proposed appointment time.",
                    choices=["yes", "no"],
                    required=True,
                ),
            ],
        )
        return

    logging.info("No open slots found for %s %s.", first_name, last_name)
    call.hangup(
        final_instructions=(
            f"Apologize to {first_name} and let them know we don't have any openings "
            f"matching their preferences right now. Let them know a scheduling coordinator "
            "will call them back within one business day with available times. "
            "Thank them for calling Maple Medical Group."
        )
    )


@agent.on_task_complete("confirm_appointment_booking")
def on_booking_confirmed(call: guava.Call) -> None:
    confirmed = call.get_field("booking_confirmed") or ""
    first_name = call.get_field("first_name")
    last_name = call.get_field("last_name")
    reason = call.get_field("reason_for_visit")

    headers = call.get_variable("headers") or {}
    patient_id = call.get_variable("patient_id")
    appt_id = call.get_variable("appt_id") or ""
    display_time = call.get_variable("display_time") or ""

    if confirmed.lower() != "yes":
        call.hangup(
            final_instructions=(
                f"Acknowledge that {first_name} can't make that time. "
                "Let them know a scheduling coordinator will follow up with additional options. "
                "Thank them for calling."
            )
        )
        return

    success = False
    if patient_id and appt_id:
        try:
            success = book_appointment(
                appt_id,
                patient_id,
                f"Booked via phone — {first_name} {last_name}. Reason: {reason}",
                headers,
            )
            logging.info("Appointment %s booked: %s", appt_id, success)
        except Exception as e:
            logging.error("Failed to book appointment %s: %s", appt_id, e)

    result = {
        "patient_id": patient_id,
        "appointment_id": appt_id,
        "display_time": display_time,
        "reason": reason,
        "booked": success,
    }
    print(json.dumps(result, indent=2))

    call.hangup(
        final_instructions=(
            f"Confirm to {first_name} that their appointment has been booked for {display_time} "
            "at Maple Medical Group. Remind them to arrive 10 minutes early and bring "
            "their insurance card and a photo ID. "
            "Let them know they will receive a confirmation call or text. "
            "Thank them for calling and wish them a great day."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])

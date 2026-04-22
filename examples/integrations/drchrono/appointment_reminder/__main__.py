import guava
import os
import logging
from guava import logging_utils
import argparse
import requests


ACCESS_TOKEN = os.environ["DRCHRONO_ACCESS_TOKEN"]
DOCTOR_ID = int(os.environ["DRCHRONO_DOCTOR_ID"])
OFFICE_ID = int(os.environ["DRCHRONO_OFFICE_ID"])
HEADERS = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
BASE_URL = "https://app.drchrono.com/api"


def get_appointment(appointment_id: str) -> dict:
    """Fetch a single appointment by ID."""
    resp = requests.get(
        f"{BASE_URL}/appointments/{appointment_id}",
        headers=HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def update_appointment_status(appointment_id: str, status: str) -> dict:
    """Update the status of an appointment (e.g., 'Confirmed' or 'Cancelled')."""
    resp = requests.patch(
        f"{BASE_URL}/appointments/{appointment_id}",
        headers=HEADERS,
        json={"status": status},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def log_call(patient_id: str, notes: str) -> dict:
    """Log a call record in DrChrono."""
    resp = requests.post(
        f"{BASE_URL}/call_logs",
        headers=HEADERS,
        json={
            "patient": int(patient_id),
            "notes": notes,
            "called_by": DOCTOR_ID,
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


agent = guava.Agent(
    name="Sam",
    organization="Oakridge Family Medicine",
    purpose="to remind patients of upcoming appointments and confirm their attendance",
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")
    appointment_id = call.get_variable("appointment_id")

    # Fetch appointment details
    appointment = None
    try:
        appointment = get_appointment(appointment_id)
        logging.info(
            "Fetched appointment %s: scheduled_time=%s, reason=%s",
            appointment_id,
            appointment.get("scheduled_time"),
            appointment.get("reason"),
        )
    except Exception as e:
        logging.error("Failed to fetch appointment %s pre-call: %s", appointment_id, e)

    scheduled_time = appointment.get("scheduled_time", "your upcoming appointment") if appointment else "your upcoming appointment"
    reason = appointment.get("reason", "") if appointment else ""
    duration = appointment.get("duration", 30) if appointment else 30

    call.data = {
        "appt_display": scheduled_time,
        "appt_reason": reason,
        "appt_duration": duration,
    }

    call.reach_person(contact_full_name=patient_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    patient_name = call.get_variable("patient_name")
    appt_display = call.data.get("appt_display", "your upcoming appointment")
    appt_reason = call.data.get("appt_reason", "")
    appt_duration = call.data.get("appt_duration", 30)

    if outcome == "unavailable":
        logging.info("Unable to reach %s for appointment reminder.", patient_name)
        call.hangup(
            final_instructions=(
                f"Leave a brief voicemail for {patient_name} from Oakridge Family Medicine. "
                f"Let them know you're calling to remind them about their appointment on {appt_display}. "
                "Ask them to call back to confirm or cancel. Keep it friendly and concise."
            )
        )
    elif outcome == "available":
        reason_clause = f" for {appt_reason}" if appt_reason else ""
        call.set_task(
            "save_results",
            objective=(
                f"Remind {patient_name} of their upcoming appointment{reason_clause} "
                f"at Oakridge Family Medicine scheduled for {appt_display} "
                f"({appt_duration} minutes). Confirm whether they will attend, "
                "ask if they have any questions, and update the appointment status accordingly."
            ),
            checklist=[
                guava.Say(
                    f"Hi {patient_name}, this is Sam calling from Oakridge Family Medicine. "
                    f"I'm calling to remind you about your upcoming appointment{' for ' + appt_reason if appt_reason else ''} "
                    f"scheduled for {appt_display}. It's about {appt_duration} minutes long."
                ),
                guava.Field(
                    key="confirmation_status",
                    field_type="multiple_choice",
                    description=(
                        "Ask if they plan to attend the appointment. "
                        "Options: confirmed (they will be there), need-to-reschedule, or cancel."
                    ),
                    choices=["confirmed", "need-to-reschedule", "cancel"],
                    required=True,
                ),
                guava.Field(
                    key="has_questions",
                    field_type="multiple_choice",
                    description="Ask if they have any questions about their appointment or what to prepare.",
                    choices=["yes", "no"],
                    required=True,
                ),
                guava.Field(
                    key="questions_or_notes",
                    field_type="text",
                    description=(
                        "If they said yes to having questions, ask them to share their question or concern. "
                        "Capture it to pass along to the care team. Skip if they said no."
                    ),
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("save_results")
def on_save_results(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")
    patient_id = call.get_variable("patient_id")
    appointment_id = call.get_variable("appointment_id")
    appt_display = call.data.get("appt_display", "your upcoming appointment")

    confirmation_status = call.get_field("confirmation_status") or "confirmed"
    has_questions = call.get_field("has_questions") or "no"
    questions_or_notes = call.get_field("questions_or_notes") or ""

    # Map collected status to DrChrono appointment status
    if confirmation_status == "confirmed":
        new_status = "Confirmed"
    elif confirmation_status == "cancel":
        new_status = "Cancelled"
    else:
        # need-to-reschedule — mark cancelled; office will follow up
        new_status = "Cancelled"

    try:
        update_appointment_status(appointment_id, new_status)
        logging.info("Appointment %s status updated to '%s'", appointment_id, new_status)
    except Exception as e:
        logging.error("Failed to update appointment %s status: %s", appointment_id, e)

    # Build call log notes
    notes_parts = [
        f"Reminder call to {patient_name} for appointment {appointment_id}.",
        f"Response: {confirmation_status}.",
    ]
    if questions_or_notes:
        notes_parts.append(f"Patient question/note: {questions_or_notes}")
    call_notes = " ".join(notes_parts)

    try:
        log_call(patient_id, call_notes)
        logging.info("Call logged for patient %s", patient_id)
    except Exception as e:
        logging.error("Failed to log call for patient %s: %s", patient_id, e)

    if confirmation_status == "confirmed":
        call.hangup(
            final_instructions=(
                f"Thank {patient_name} for confirming. "
                "Remind them to arrive 10 minutes early and bring their insurance card and a photo ID. "
                + (
                    "Let them know their question has been passed along to the care team and "
                    "someone will follow up before their visit. "
                    if questions_or_notes else ""
                )
                + "Wish them a great day."
            )
        )
    elif confirmation_status == "need-to-reschedule":
        call.hangup(
            final_instructions=(
                f"Let {patient_name} know their appointment has been cancelled and "
                "that a team member from Oakridge Family Medicine will call them back "
                "to find a new time that works. Apologize for any inconvenience and wish them well."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Let {patient_name} know their appointment has been cancelled. "
                "Encourage them to call back whenever they're ready to schedule again. "
                "Thank them for letting us know and wish them a great day."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound appointment reminder call via DrChrono."
    )
    parser.add_argument("phone", help="Patient phone number (E.164, e.g. +15551234567)")
    parser.add_argument("--appointment-id", required=True, help="DrChrono appointment ID")
    parser.add_argument("--name", required=True, help="Patient's full name")
    parser.add_argument("--patient-id", required=True, help="DrChrono patient ID")
    args = parser.parse_args()

    logging.info(
        "Sending appointment reminder to %s (%s), appointment ID: %s",
        args.name, args.phone, args.appointment_id,
    )

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "patient_name": args.name,
            "patient_id": args.patient_id,
            "appointment_id": args.appointment_id,
        },
    )

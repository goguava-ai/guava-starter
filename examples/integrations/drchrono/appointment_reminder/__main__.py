import guava
import os
import logging
import argparse
import requests

logging.basicConfig(level=logging.INFO)

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


class AppointmentReminderController(guava.CallController):
    def __init__(self, patient_name: str, patient_id: str, appointment_id: str):
        super().__init__()
        self.patient_name = patient_name
        self.patient_id = patient_id
        self.appointment_id = appointment_id
        self.appointment = None

        # Pre-call: fetch appointment details
        try:
            self.appointment = get_appointment(appointment_id)
            logging.info(
                "Fetched appointment %s: scheduled_time=%s, reason=%s",
                appointment_id,
                self.appointment.get("scheduled_time"),
                self.appointment.get("reason"),
            )
        except Exception as e:
            logging.error("Failed to fetch appointment %s pre-call: %s", appointment_id, e)

        scheduled_time = self.appointment.get("scheduled_time", "your upcoming appointment") if self.appointment else "your upcoming appointment"
        reason = self.appointment.get("reason", "") if self.appointment else ""
        duration = self.appointment.get("duration", 30) if self.appointment else 30

        self.appt_display = scheduled_time
        self.appt_reason = reason
        self.appt_duration = duration

        self.set_persona(
            organization_name="Oakridge Family Medicine",
            agent_name="Sam",
            agent_purpose="to remind patients of upcoming appointments and confirm their attendance",
        )

        self.reach_person(
            contact_full_name=patient_name,
            on_success=self.begin_call,
            on_failure=self.recipient_unavailable,
        )

    def begin_call(self):
        reason_clause = f" for {self.appt_reason}" if self.appt_reason else ""
        self.set_task(
            objective=(
                f"Remind {self.patient_name} of their upcoming appointment{reason_clause} "
                f"at Oakridge Family Medicine scheduled for {self.appt_display} "
                f"({self.appt_duration} minutes). Confirm whether they will attend, "
                "ask if they have any questions, and update the appointment status accordingly."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.patient_name}, this is Sam calling from Oakridge Family Medicine. "
                    f"I'm calling to remind you about your upcoming appointment{' for ' + self.appt_reason if self.appt_reason else ''} "
                    f"scheduled for {self.appt_display}. It's about {self.appt_duration} minutes long."
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
            on_complete=self.save_results,
        )

    def save_results(self):
        confirmation_status = self.get_field("confirmation_status") or "confirmed"
        has_questions = self.get_field("has_questions") or "no"
        questions_or_notes = self.get_field("questions_or_notes") or ""

        # Map collected status to DrChrono appointment status
        if confirmation_status == "confirmed":
            new_status = "Confirmed"
        elif confirmation_status == "cancel":
            new_status = "Cancelled"
        else:
            # need-to-reschedule — mark cancelled; office will follow up
            new_status = "Cancelled"

        try:
            update_appointment_status(self.appointment_id, new_status)
            logging.info("Appointment %s status updated to '%s'", self.appointment_id, new_status)
        except Exception as e:
            logging.error("Failed to update appointment %s status: %s", self.appointment_id, e)

        # Build call log notes
        notes_parts = [
            f"Reminder call to {self.patient_name} for appointment {self.appointment_id}.",
            f"Response: {confirmation_status}.",
        ]
        if questions_or_notes:
            notes_parts.append(f"Patient question/note: {questions_or_notes}")
        call_notes = " ".join(notes_parts)

        try:
            log_call(self.patient_id, call_notes)
            logging.info("Call logged for patient %s", self.patient_id)
        except Exception as e:
            logging.error("Failed to log call for patient %s: %s", self.patient_id, e)

        if confirmation_status == "confirmed":
            self.hangup(
                final_instructions=(
                    f"Thank {self.patient_name} for confirming. "
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
            self.hangup(
                final_instructions=(
                    f"Let {self.patient_name} know their appointment has been cancelled and "
                    "that a team member from Oakridge Family Medicine will call them back "
                    "to find a new time that works. Apologize for any inconvenience and wish them well."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    f"Let {self.patient_name} know their appointment has been cancelled. "
                    "Encourage them to call back whenever they're ready to schedule again. "
                    "Thank them for letting us know and wish them a great day."
                )
            )

    def recipient_unavailable(self):
        logging.info("Unable to reach %s for appointment reminder.", self.patient_name)
        self.hangup(
            final_instructions=(
                f"Leave a brief voicemail for {self.patient_name} from Oakridge Family Medicine. "
                f"Let them know you're calling to remind them about their appointment on {self.appt_display}. "
                "Ask them to call back to confirm or cancel. Keep it friendly and concise."
            )
        )


if __name__ == "__main__":
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

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=AppointmentReminderController(
            patient_name=args.name,
            patient_id=args.patient_id,
            appointment_id=args.appointment_id,
        ),
    )

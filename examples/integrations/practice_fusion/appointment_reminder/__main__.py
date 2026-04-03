import guava
import os
import logging
import argparse
import requests
from datetime import datetime

logging.basicConfig(level=logging.INFO)

BASE_URL = os.environ.get("PRACTICE_FUSION_FHIR_BASE_URL", "https://api.practicefusion.com/fhir/r4")


def get_headers():
    return {
        "Authorization": f"Bearer {os.environ['PRACTICE_FUSION_ACCESS_TOKEN']}",
        "Content-Type": "application/json",
    }


def get_appointment(appointment_id: str) -> dict:
    """Fetch a single Appointment resource by ID."""
    resp = requests.get(
        f"{BASE_URL}/Appointment/{appointment_id}",
        headers=get_headers(),
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def patch_appointment(appointment_id: str, status: str, cancellation_reason: str | None = None) -> dict:
    """Update the status (and optionally cancellation comment) on an Appointment resource."""
    payload: dict = {
        "resourceType": "Appointment",
        "id": appointment_id,
        "status": status,
    }
    if cancellation_reason:
        payload["comment"] = f"Patient cancellation reason: {cancellation_reason}"
    resp = requests.patch(
        f"{BASE_URL}/Appointment/{appointment_id}",
        headers=get_headers(),
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def format_appointment_start(appointment: dict) -> str:
    """Return a human-readable date/time string for the appointment's start time."""
    start_str = appointment.get("start", "")
    try:
        dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
        return dt.strftime("%A, %B %-d at %-I:%M %p")
    except (ValueError, AttributeError):
        return start_str or "your upcoming appointment"


def get_provider_display(appointment: dict) -> str:
    """Return the display name of the practitioner participant, if present."""
    for participant in appointment.get("participant", []):
        actor = participant.get("actor", {})
        ref = actor.get("reference", "")
        if ref.startswith("Practitioner"):
            return actor.get("display", "")
    return ""


class AppointmentReminderController(guava.CallController):
    def __init__(self, patient_name: str, patient_id: str, appointment_id: str):
        super().__init__()
        self.patient_name = patient_name
        self.patient_id = patient_id
        self.appointment_id = appointment_id
        self._appointment_description = "your upcoming appointment"
        self._provider_name = ""

        self.set_persona(
            organization_name="Riverside Family Medicine",
            agent_name="Taylor",
            agent_purpose=(
                "to remind patients of their upcoming appointments at Riverside Family Medicine "
                "and record whether they plan to attend or need to cancel"
            ),
        )

        self.reach_person(
            contact_full_name=self.patient_name,
            on_success=self.deliver_reminder,
            on_failure=self.leave_voicemail,
        )

    def _fetch_appointment_details(self):
        """Fetch the FHIR Appointment resource and cache a readable description."""
        try:
            appointment = get_appointment(self.appointment_id)
            self._appointment_description = format_appointment_start(appointment)
            self._provider_name = get_provider_display(appointment)
            logging.info(
                "Appointment %s: %s with %s",
                self.appointment_id,
                self._appointment_description,
                self._provider_name or "provider",
            )
        except Exception as exc:
            logging.error("Failed to fetch appointment %s: %s", self.appointment_id, exc)

    def deliver_reminder(self):
        self._fetch_appointment_details()

        provider_clause = f" with {self._provider_name}" if self._provider_name else ""

        self.set_task(
            objective=(
                f"Remind {self.patient_name} of their appointment{provider_clause} at Riverside Family Medicine "
                f"on {self._appointment_description}. Confirm whether they plan to attend or need to cancel."
            ),
            checklist=[
                guava.Say(
                    f"Hello {self.patient_name}, this is Taylor calling from Riverside Family Medicine. "
                    f"I'm reaching out to remind you of your appointment{provider_clause} scheduled for "
                    f"{self._appointment_description}."
                ),
                guava.Field(
                    key="confirmed",
                    field_type="multiple_choice",
                    description=(
                        "Ask whether the patient plans to keep their appointment or needs to cancel it. "
                        "Capture their response."
                    ),
                    choices=["confirm", "cancel"],
                    required=True,
                ),
                guava.Field(
                    key="cancellation_reason",
                    field_type="text",
                    description=(
                        "If the patient chose to cancel, ask for a brief reason "
                        "(e.g., scheduling conflict, feeling better, transportation issue). "
                        "Only collect this field if they said they need to cancel."
                    ),
                    required=False,
                ),
            ],
            on_complete=self.handle_confirmation,
        )

    def handle_confirmation(self):
        confirmed = self.get_field("confirmed")
        cancellation_reason = self.get_field("cancellation_reason")

        cancelled = confirmed and confirmed.strip().lower() == "cancel"
        new_status = "cancelled" if cancelled else "booked"

        # Post-call: patch the appointment status in Practice Fusion.
        # For cancellations, include the patient-provided reason as a comment.
        try:
            patch_appointment(
                self.appointment_id,
                new_status,
                cancellation_reason if cancelled else None,
            )
            logging.info(
                "Appointment %s patched to status=%s",
                self.appointment_id,
                new_status,
            )
        except Exception as exc:
            logging.error("Failed to patch appointment %s: %s", self.appointment_id, exc)

        if cancelled:
            self.hangup(
                final_instructions=(
                    f"Let {self.patient_name} know their appointment has been cancelled and that "
                    "a member of the Riverside Family Medicine scheduling team will follow up to "
                    "help them find a new time whenever they are ready. Thank them warmly."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    f"Thank {self.patient_name} for confirming. Let them know we look forward to "
                    "seeing them. Remind them to arrive about 10 minutes early and to bring a photo "
                    "ID and insurance card if they have not visited recently. Wish them a great day."
                )
            )

    def leave_voicemail(self):
        self.hangup(
            final_instructions=(
                f"Leave a brief, friendly voicemail for {self.patient_name} on behalf of Riverside "
                f"Family Medicine reminding them of their appointment on "
                f"{self._appointment_description or 'the scheduled date'}. "
                "Ask them to call the office back if they have questions or need to reschedule. "
                "Do not leave any clinical details in the voicemail. Keep it under 30 seconds."
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Outbound appointment reminder call for Riverside Family Medicine via Practice Fusion FHIR R4."
    )
    parser.add_argument("phone", help="Patient phone number in E.164 format (e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Patient full name")
    parser.add_argument("--patient-id", required=True, help="Practice Fusion FHIR Patient resource ID")
    parser.add_argument("--appointment-id", required=True, help="Practice Fusion FHIR Appointment resource ID")
    args = parser.parse_args()

    logging.info(
        "Initiating appointment reminder call to %s (%s), appointment %s",
        args.name,
        args.phone,
        args.appointment_id,
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

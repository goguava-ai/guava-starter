import guava
import os
import logging
import requests

logging.basicConfig(level=logging.INFO)

ACCESS_TOKEN = os.environ["DRCHRONO_ACCESS_TOKEN"]
DOCTOR_ID = int(os.environ["DRCHRONO_DOCTOR_ID"])
OFFICE_ID = int(os.environ["DRCHRONO_OFFICE_ID"])
HEADERS = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
BASE_URL = "https://app.drchrono.com/api"


def search_patient_by_email(email: str) -> dict | None:
    """Search for a patient by email address. Returns the first match or None."""
    resp = requests.get(
        f"{BASE_URL}/patients",
        headers=HEADERS,
        params={"email": email},
        timeout=10,
    )
    resp.raise_for_status()
    results = resp.json().get("results", [])
    return results[0] if results else None


def create_patient(first_name: str, last_name: str, email: str, dob: str) -> dict:
    """Create a new patient record in DrChrono."""
    resp = requests.post(
        f"{BASE_URL}/patients",
        headers=HEADERS,
        json={
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "date_of_birth": dob,
            "doctor": DOCTOR_ID,
            "office": OFFICE_ID,
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def create_appointment(patient_id: int, reason: str, scheduled_time: str) -> dict:
    """Create an appointment for the given patient."""
    resp = requests.post(
        f"{BASE_URL}/appointments",
        headers=HEADERS,
        json={
            "patient": patient_id,
            "doctor": DOCTOR_ID,
            "office": OFFICE_ID,
            "exam_room": 1,
            "scheduled_time": scheduled_time,
            "duration": 30,
            "reason": reason,
            "status": "Confirmed",
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


TIME_MAP = {
    "morning": "09:00:00",
    "afternoon": "14:00:00",
    "evening": "17:00:00",
}


class AppointmentSchedulingController(guava.CallController):
    def __init__(self):
        super().__init__()
        self.patient = None

        self.set_persona(
            organization_name="Oakridge Family Medicine",
            agent_name="Jordan",
            agent_purpose="to help patients schedule appointments at Oakridge Family Medicine",
        )

        self.set_task(
            objective=(
                "A patient has called Oakridge Family Medicine to schedule an appointment. "
                "Collect their contact information, verify or create their patient record, "
                "and capture their scheduling preferences."
            ),
            checklist=[
                guava.Say(
                    "Thank you for calling Oakridge Family Medicine. "
                    "My name is Jordan and I'd be happy to help you schedule an appointment today."
                ),
                guava.Field(
                    key="patient_email",
                    field_type="text",
                    description="Ask for the caller's email address so we can look up their record.",
                    required=True,
                ),
                guava.Field(
                    key="first_name",
                    field_type="text",
                    description=(
                        "If this is a new patient (we couldn't find them by email), ask for their first name. "
                        "Skip this question if they are already in our system."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="last_name",
                    field_type="text",
                    description=(
                        "If this is a new patient, ask for their last name. "
                        "Skip this question if they are already in our system."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="date_of_birth",
                    field_type="text",
                    description=(
                        "Ask for their date of birth for verification. "
                        "Capture in YYYY-MM-DD format."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="appointment_reason",
                    field_type="text",
                    description="Ask what brings them in — the reason for the appointment.",
                    required=True,
                ),
                guava.Field(
                    key="preferred_date",
                    field_type="text",
                    description=(
                        "Ask for their preferred appointment date. "
                        "Ask them to give a specific date, for example 'March 15th'."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="preferred_time",
                    field_type="multiple_choice",
                    description="Ask whether they prefer a morning, afternoon, or evening appointment.",
                    choices=["morning", "afternoon", "evening"],
                    required=True,
                ),
                guava.Field(
                    key="appointment_type",
                    field_type="multiple_choice",
                    description=(
                        "Ask what type of appointment this is. "
                        "Options: wellness visit, sick visit, follow-up, specialist referral, or other."
                    ),
                    choices=["wellness-visit", "sick-visit", "follow-up", "specialist-referral", "other"],
                    required=True,
                ),
            ],
            on_complete=self.handle_complete,
        )

        self.accept_call()

    def handle_complete(self):
        email = self.get_field("patient_email") or ""
        first_name = self.get_field("first_name") or ""
        last_name = self.get_field("last_name") or ""
        dob = self.get_field("date_of_birth") or ""
        reason = self.get_field("appointment_reason") or "General visit"
        preferred_time = self.get_field("preferred_time") or "morning"
        appointment_type = self.get_field("appointment_type") or "other"

        # Look up or create patient
        patient_id = None
        patient_first = first_name
        try:
            existing = search_patient_by_email(email)
            if existing:
                patient_id = existing["id"]
                patient_first = existing.get("first_name", first_name)
                logging.info("Found existing patient %s (ID: %s)", patient_first, patient_id)
            elif first_name and last_name:
                new_patient = create_patient(first_name, last_name, email, dob)
                patient_id = new_patient["id"]
                logging.info("Created new patient %s %s (ID: %s)", first_name, last_name, patient_id)
            else:
                logging.warning("New patient but first/last name not collected — cannot create record.")
        except Exception as e:
            logging.error("Patient lookup/creation failed: %s", e)

        # Build a placeholder scheduled time — scheduling team will confirm exact time
        time_str = TIME_MAP.get(preferred_time, "09:00:00")
        scheduled_time = f"2025-01-15T{time_str}"

        appt_id = None
        if patient_id:
            try:
                full_reason = f"{appointment_type.replace('-', ' ').title()} — {reason}"
                appt = create_appointment(patient_id, full_reason, scheduled_time)
                appt_id = appt.get("id")
                logging.info("Created appointment ID %s for patient %s", appt_id, patient_id)
            except Exception as e:
                logging.error("Appointment creation failed: %s", e)

        if appt_id:
            self.hangup(
                final_instructions=(
                    f"Let the caller know their appointment request has been received. "
                    f"Tell them that the scheduling team at Oakridge Family Medicine will call them back "
                    f"to confirm the exact date and time based on their preference of {preferred_time}. "
                    "Ask them to have their insurance card ready for the visit. "
                    "Thank them for calling and wish them a great day."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    "Apologize to the caller and let them know there was a technical issue processing "
                    "their appointment request. Ask them to call back or hold while a team member assists. "
                    "Thank them for their patience."
                )
            )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=AppointmentSchedulingController,
    )

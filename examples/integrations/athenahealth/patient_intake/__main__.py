import guava
import os
import logging
import argparse
import requests

logging.basicConfig(level=logging.INFO)

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


def get_patient_medications(patient_id: str, headers: dict) -> list:
    resp = requests.get(
        f"{BASE_URL}/patients/{patient_id}/medications",
        headers=headers,
        timeout=10,
    )
    if not resp.ok:
        return []
    return resp.json().get("medications", [])


def get_patient_allergies(patient_id: str, headers: dict) -> list:
    resp = requests.get(
        f"{BASE_URL}/patients/{patient_id}/allergies",
        headers=headers,
        timeout=10,
    )
    if not resp.ok:
        return []
    return resp.json().get("allergies", [])


def post_intake_document(patient_id: str, content: str, headers: dict) -> bool:
    """Posts a pre-visit intake summary as a document to the patient chart."""
    resp = requests.post(
        f"{BASE_URL}/patients/{patient_id}/documents",
        headers={**headers, "Content-Type": "application/x-www-form-urlencoded"},
        data={
            "documentsubclass": "LETTER",
            "internalnote": content,
            "status": "CLOSED",
        },
        timeout=10,
    )
    return resp.ok


class PatientIntakeController(guava.CallController):
    def __init__(self, patient_name: str, patient_id: str, appointment_time: str):
        super().__init__()
        self.patient_name = patient_name
        self.patient_id = patient_id
        self.appointment_time = appointment_time
        self.headers = {}
        self.existing_meds: list = []
        self.existing_allergies: list = []

        try:
            token = get_access_token()
            self.headers = {"Authorization": f"Bearer {token}"}
            self.existing_meds = get_patient_medications(patient_id, self.headers)
            self.existing_allergies = get_patient_allergies(patient_id, self.headers)
            logging.info(
                "Pre-call data loaded for patient %s: %d meds, %d allergies",
                patient_id, len(self.existing_meds), len(self.existing_allergies),
            )
        except Exception as e:
            logging.error("Failed to load patient pre-call data for %s: %s", patient_id, e)

        med_names = [m.get("medicationname", "") for m in self.existing_meds if m.get("medicationname")]
        allergy_names = [a.get("allergenname", "") for a in self.existing_allergies if a.get("allergenname")]

        meds_context = (
            f"Medications on file: {', '.join(med_names)}. "
            "Confirm whether this list is still current and ask about any new medications."
            if med_names else
            "No medications on file. Ask what medications they are currently taking."
        )
        allergies_context = (
            f"Allergies on file: {', '.join(allergy_names)}. "
            "Confirm accuracy and ask about any new allergies."
            if allergy_names else
            "No allergies on file. Ask if they have any known drug or environmental allergies."
        )

        self.set_persona(
            organization_name="Maple Medical Group",
            agent_name="Avery",
            agent_purpose=(
                "to complete pre-visit intake for patients before their appointments"
            ),
        )

        self.set_task(
            objective=(
                f"Complete pre-visit intake for {patient_name} ahead of their appointment "
                f"on {appointment_time}. Collect their chief complaint, confirm current "
                "medications and allergies, and note any changes since their last visit."
            ),
            checklist=[
                guava.Say(
                    f"Hi {patient_name}, this is Avery calling from Maple Medical Group. "
                    f"I'm calling to complete a quick pre-visit intake ahead of your appointment "
                    f"on {appointment_time}. It should only take a few minutes."
                ),
                guava.Field(
                    key="chief_complaint",
                    field_type="text",
                    description=(
                        "Ask what the main reason is for their upcoming visit. "
                        "What symptoms or concerns are they coming in for?"
                    ),
                    required=True,
                ),
                guava.Field(
                    key="medications_confirmed",
                    field_type="text",
                    description=meds_context,
                    required=True,
                ),
                guava.Field(
                    key="allergies_confirmed",
                    field_type="text",
                    description=allergies_context,
                    required=True,
                ),
                guava.Field(
                    key="recent_changes",
                    field_type="text",
                    description=(
                        "Ask if there have been any significant health changes since their last visit — "
                        "new diagnoses, hospitalizations, or changes in symptoms."
                    ),
                    required=False,
                ),
            ],
            on_complete=self.save_intake,
        )

        self.reach_person(
            contact_full_name=self.patient_name,
            on_success=lambda: None,  # task already set; will run after reach_person
            on_failure=self.recipient_unavailable,
        )

    def save_intake(self):
        complaint = self.get_field("chief_complaint") or ""
        meds = self.get_field("medications_confirmed") or ""
        allergies = self.get_field("allergies_confirmed") or ""
        changes = self.get_field("recent_changes") or "None reported"

        summary = (
            f"Pre-visit intake — {self.appointment_time}\n"
            f"Chief complaint: {complaint}\n"
            f"Medications: {meds}\n"
            f"Allergies: {allergies}\n"
            f"Recent changes: {changes}"
        )
        logging.info("Intake summary for patient %s:\n%s", self.patient_id, summary)

        try:
            posted = post_intake_document(self.patient_id, summary, self.headers)
            logging.info("Intake document posted to chart: %s", posted)
        except Exception as e:
            logging.error("Failed to post intake document for patient %s: %s", self.patient_id, e)

        self.hangup(
            final_instructions=(
                f"Thank {self.patient_name} for completing the intake. "
                "Let them know the care team will review this before their visit. "
                "Remind them to arrive 10–15 minutes early and bring their insurance card. "
                "Wish them a great day."
            )
        )

    def recipient_unavailable(self):
        logging.info("Unable to reach %s for pre-visit intake.", self.patient_name)
        self.hangup(
            final_instructions=(
                f"Leave a brief voicemail for {self.patient_name} from Maple Medical Group. "
                "Let them know you're calling to complete a pre-visit intake before their "
                f"appointment on {self.appointment_time} and ask them to call back. "
                "Keep it friendly and concise."
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Outbound pre-visit patient intake via Athenahealth."
    )
    parser.add_argument("phone", help="Patient phone number (E.164, e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Patient's full name")
    parser.add_argument("--patient-id", required=True, help="Athenahealth patient ID")
    parser.add_argument("--appointment", required=True, help="Appointment date/time (display string)")
    args = parser.parse_args()

    logging.info(
        "Starting pre-visit intake call to %s (%s), appointment: %s",
        args.name, args.phone, args.appointment,
    )

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=PatientIntakeController(
            patient_name=args.name,
            patient_id=args.patient_id,
            appointment_time=args.appointment,
        ),
    )

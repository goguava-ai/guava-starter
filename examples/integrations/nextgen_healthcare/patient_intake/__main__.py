import guava
import os
import logging
from guava import logging_utils
import argparse
import requests
import base64



def get_access_token() -> str:
    resp = requests.post(
        os.environ["NEXTGEN_TOKEN_URL"],
        data={"grant_type": "client_credentials", "scope": "system/*.read system/*.write"},
        auth=(os.environ["NEXTGEN_CLIENT_ID"], os.environ["NEXTGEN_CLIENT_SECRET"]),
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def get_medications(patient_id: str, headers: dict) -> list:
    base_url = os.environ["NEXTGEN_BASE_URL"]
    resp = requests.get(
        f"{base_url}/MedicationRequest",
        headers=headers,
        params={"patient": patient_id, "status": "active", "_count": "10"},
        timeout=10,
    )
    if not resp.ok:
        return []
    return resp.json().get("entry", [])


def get_allergies(patient_id: str, headers: dict) -> list:
    base_url = os.environ["NEXTGEN_BASE_URL"]
    resp = requests.get(
        f"{base_url}/AllergyIntolerance",
        headers=headers,
        params={"patient": patient_id, "_count": "10"},
        timeout=10,
    )
    if not resp.ok:
        return []
    return resp.json().get("entry", [])


def post_document_reference(patient_id: str, content: str, headers: dict) -> bool:
    base_url = os.environ["NEXTGEN_BASE_URL"]
    encoded = base64.b64encode(content.encode()).decode()
    payload = {
        "resourceType": "DocumentReference",
        "status": "current",
        "type": {
            "coding": [{"system": "http://loinc.org", "code": "34117-2", "display": "History and physical note"}]
        },
        "subject": {"reference": f"Patient/{patient_id}"},
        "content": [{"attachment": {"contentType": "text/plain", "data": encoded, "title": "Pre-Visit Intake"}}],
    }
    resp = requests.post(f"{base_url}/DocumentReference", headers=headers, json=payload, timeout=10)
    return resp.ok


class PatientIntakeController(guava.CallController):
    def __init__(self, patient_name: str, patient_id: str, appointment_time: str):
        super().__init__()
        self.patient_name = patient_name
        self.patient_id = patient_id
        self.appointment_time = appointment_time
        self.headers = {}

        try:
            token = get_access_token()
            self.headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        except Exception as e:
            logging.error("Token error: %s", e)

        med_names, allergy_names = [], []
        try:
            meds = get_medications(patient_id, self.headers)
            for e in meds:
                r = e.get("resource", {})
                name = r.get("medicationCodeableConcept", {}).get("text", "") or r.get("medicationReference", {}).get("display", "")
                if name:
                    med_names.append(name)
        except Exception as e:
            logging.warning("Could not load medications: %s", e)

        try:
            allergies = get_allergies(patient_id, self.headers)
            for e in allergies:
                r = e.get("resource", {})
                name = r.get("code", {}).get("text", "")
                if name:
                    allergy_names.append(name)
        except Exception as e:
            logging.warning("Could not load allergies: %s", e)

        meds_context = (
            f"Medications on file: {', '.join(med_names)}. Confirm if current and ask about any new ones."
            if med_names else "No medications on file. Ask what medications they take."
        )
        allergies_context = (
            f"Allergies on file: {', '.join(allergy_names)}. Confirm accuracy and ask about new allergies."
            if allergy_names else "No allergies on file. Ask about any known allergies."
        )

        self.set_persona(
            organization_name="Metro Specialty Clinic",
            agent_name="Morgan",
            agent_purpose="to complete pre-visit intake for patients",
        )

        self.set_task(
            objective=f"Complete pre-visit intake for {patient_name} ahead of their appointment on {appointment_time}.",
            checklist=[
                guava.Say(
                    f"Hi {patient_name}, this is Morgan from Metro Specialty Clinic. "
                    f"I'm calling to complete a quick intake before your appointment on {appointment_time}."
                ),
                guava.Field(
                    key="chief_complaint",
                    field_type="text",
                    description="Ask the main reason for today's visit.",
                    required=True,
                ),
                guava.Field(
                    key="medications",
                    field_type="text",
                    description=meds_context,
                    required=True,
                ),
                guava.Field(
                    key="allergies",
                    field_type="text",
                    description=allergies_context,
                    required=True,
                ),
                guava.Field(
                    key="recent_changes",
                    field_type="text",
                    description="Ask about significant health changes since their last visit.",
                    required=False,
                ),
            ],
            on_complete=self.save_intake,
        )

        self.reach_person(
            contact_full_name=self.patient_name,
            on_success=lambda: None,
            on_failure=lambda: self.hangup(
                final_instructions=(
                    f"Leave a voicemail for {self.patient_name} from Metro Specialty Clinic "
                    f"asking them to call back for a quick pre-visit intake before {self.appointment_time}."
                )
            ),
        )

    def save_intake(self):
        complaint = self.get_field("chief_complaint") or ""
        meds = self.get_field("medications") or ""
        allergies = self.get_field("allergies") or ""
        changes = self.get_field("recent_changes") or "None reported"

        note = (
            f"Pre-Visit Intake — {self.appointment_time}\n"
            f"Chief complaint: {complaint}\n"
            f"Medications: {meds}\n"
            f"Allergies: {allergies}\n"
            f"Recent changes: {changes}"
        )
        logging.info("Intake for patient %s:\n%s", self.patient_id, note)

        try:
            posted = post_document_reference(self.patient_id, note, self.headers)
            logging.info("DocumentReference posted: %s", posted)
        except Exception as e:
            logging.error("Failed to post document: %s", e)

        self.hangup(
            final_instructions=(
                f"Thank {self.patient_name} for completing intake. Let them know the care team "
                "will review their information. Remind them to arrive 10 minutes early. "
                "Wish them a great day."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(description="Outbound patient intake via NextGen FHIR.")
    parser.add_argument("phone", help="Patient phone number (E.164)")
    parser.add_argument("--name", required=True)
    parser.add_argument("--patient-id", required=True)
    parser.add_argument("--appointment", required=True)
    args = parser.parse_args()

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=PatientIntakeController(
            patient_name=args.name,
            patient_id=args.patient_id,
            appointment_time=args.appointment,
        ),
    )

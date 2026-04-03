import guava
import os
import logging
import argparse
import requests

logging.basicConfig(level=logging.INFO)


def get_access_token() -> str:
    resp = requests.post(
        os.environ["ECW_TOKEN_URL"],
        data={"grant_type": "client_credentials", "scope": "system/*.read system/*.write"},
        auth=(os.environ["ECW_CLIENT_ID"], os.environ["ECW_CLIENT_SECRET"]),
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def get_medications(patient_id: str, headers: dict) -> list:
    base_url = os.environ["ECW_BASE_URL"]
    resp = requests.get(
        f"{base_url}/MedicationStatement",
        headers=headers,
        params={"patient": patient_id, "_count": "10"},
        timeout=10,
    )
    if not resp.ok:
        return []
    return resp.json().get("entry", [])


def get_allergies(patient_id: str, headers: dict) -> list:
    base_url = os.environ["ECW_BASE_URL"]
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
    """Posts a pre-visit intake note as a DocumentReference to the eClinicalWorks chart."""
    base_url = os.environ["ECW_BASE_URL"]
    import base64
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
        self.existing_meds: list = []
        self.existing_allergies: list = []

        try:
            token = get_access_token()
            self.headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            self.existing_meds = get_medications(patient_id, self.headers)
            self.existing_allergies = get_allergies(patient_id, self.headers)
            logging.info(
                "Pre-call data: patient=%s, meds=%d, allergies=%d",
                patient_id, len(self.existing_meds), len(self.existing_allergies),
            )
        except Exception as e:
            logging.error("Failed to load pre-call data for patient %s: %s", patient_id, e)

        def extract_name(entry: dict, resource_key: str, name_path: list) -> str:
            resource = entry.get("resource", {})
            obj = resource
            for key in name_path:
                obj = obj.get(key, {}) if isinstance(obj, dict) else {}
            return obj if isinstance(obj, str) else ""

        med_names = []
        for e in self.existing_meds:
            r = e.get("resource", {})
            med = r.get("medicationCodeableConcept", {}).get("text", "") or r.get("medicationReference", {}).get("display", "")
            if med:
                med_names.append(med)

        allergy_names = []
        for e in self.existing_allergies:
            r = e.get("resource", {})
            substance = r.get("code", {}).get("text", "")
            if substance:
                allergy_names.append(substance)

        meds_context = (
            f"Medications on file: {', '.join(med_names)}. Confirm if still current and ask about any new ones."
            if med_names else
            "No medications on file. Ask what medications they currently take."
        )
        allergies_context = (
            f"Allergies on file: {', '.join(allergy_names)}. Confirm accuracy and ask about new allergies."
            if allergy_names else
            "No allergies on file. Ask if they have any known drug or environmental allergies."
        )

        self.set_persona(
            organization_name="Sunrise Family Practice",
            agent_name="Sam",
            agent_purpose="to complete pre-visit intake for patients before their appointments",
        )

        self.set_task(
            objective=(
                f"Complete pre-visit intake for {patient_name} ahead of their appointment "
                f"on {appointment_time}."
            ),
            checklist=[
                guava.Say(
                    f"Hi {patient_name}, this is Sam from Sunrise Family Practice. "
                    f"I'm calling to complete a quick pre-visit check-in before your appointment "
                    f"on {appointment_time}."
                ),
                guava.Field(
                    key="chief_complaint",
                    field_type="text",
                    description="Ask what brings them in for this visit.",
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
                    description="Ask about any significant health changes since their last visit.",
                    required=False,
                ),
            ],
            on_complete=self.save_intake,
        )

        self.reach_person(
            contact_full_name=self.patient_name,
            on_success=lambda: None,
            on_failure=self.recipient_unavailable,
        )

    def save_intake(self):
        complaint = self.get_field("chief_complaint") or ""
        meds = self.get_field("medications") or ""
        allergies = self.get_field("allergies") or ""
        changes = self.get_field("recent_changes") or "None reported"

        note = (
            f"Pre-Visit Intake — {self.appointment_time}\n"
            f"Chief complaint: {complaint}\n"
            f"Current medications: {meds}\n"
            f"Allergies: {allergies}\n"
            f"Recent changes: {changes}"
        )
        logging.info("Intake for patient %s:\n%s", self.patient_id, note)

        try:
            posted = post_document_reference(self.patient_id, note, self.headers)
            logging.info("Intake DocumentReference posted: %s", posted)
        except Exception as e:
            logging.error("Failed to post intake document: %s", e)

        self.hangup(
            final_instructions=(
                f"Thank {self.patient_name} for completing intake. Let them know the care team "
                "will review their information before the visit. Remind them to arrive 10 minutes "
                "early with their insurance card. Wish them a great day."
            )
        )

    def recipient_unavailable(self):
        logging.info("Unable to reach %s for intake.", self.patient_name)
        self.hangup(
            final_instructions=(
                f"Leave a brief voicemail for {self.patient_name} from Sunrise Family Practice "
                f"asking them to call back for a quick pre-visit check-in before their "
                f"appointment on {self.appointment_time}."
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Outbound patient intake via eClinicalWorks FHIR.")
    parser.add_argument("phone", help="Patient phone number (E.164)")
    parser.add_argument("--name", required=True)
    parser.add_argument("--patient-id", required=True)
    parser.add_argument("--appointment", required=True, help="Appointment date/time display string")
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

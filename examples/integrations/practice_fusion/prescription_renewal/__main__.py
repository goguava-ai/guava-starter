import guava
import os
import logging
import requests
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)

BASE_URL = os.environ.get("PRACTICE_FUSION_FHIR_BASE_URL", "https://api.practicefusion.com/fhir/r4")


def get_headers():
    return {
        "Authorization": f"Bearer {os.environ['PRACTICE_FUSION_ACCESS_TOKEN']}",
        "Content-Type": "application/json",
    }


def search_patient(last_name: str, dob: str) -> dict | None:
    """Search for a patient by last name and date of birth. Returns the first matching resource or None."""
    resp = requests.get(
        f"{BASE_URL}/Patient",
        headers=get_headers(),
        params={"family": last_name, "birthdate": dob},
        timeout=10,
    )
    resp.raise_for_status()
    bundle = resp.json()
    entries = bundle.get("entry", [])
    if not entries:
        return None
    return entries[0]["resource"]


def get_active_medication_requests(patient_id: str) -> list[dict]:
    """Return all active MedicationRequest resources for the given patient."""
    resp = requests.get(
        f"{BASE_URL}/MedicationRequest",
        headers=get_headers(),
        params={"patient": f"Patient/{patient_id}", "status": "active"},
        timeout=10,
    )
    resp.raise_for_status()
    bundle = resp.json()
    return [entry["resource"] for entry in bundle.get("entry", [])]


def medication_display(med_request: dict) -> str:
    """Return the human-readable medication name from a MedicationRequest resource."""
    concept = med_request.get("medicationCodeableConcept", {})
    text = concept.get("text", "")
    if text:
        return text
    for coding in concept.get("coding", []):
        if coding.get("display"):
            return coding["display"]
    return "Unknown medication"


def create_medication_request(patient_id: str, source_med: dict, note_text: str) -> dict:
    """POST a new MedicationRequest with intent='proposal' to represent a patient-initiated renewal."""
    payload = {
        "resourceType": "MedicationRequest",
        "status": "active",
        "intent": "proposal",
        "medicationCodeableConcept": source_med.get("medicationCodeableConcept", {}),
        "subject": {"reference": f"Patient/{patient_id}"},
        "authoredOn": datetime.now(timezone.utc).isoformat(),
        "note": [{"text": note_text}],
    }
    resp = requests.post(
        f"{BASE_URL}/MedicationRequest",
        headers=get_headers(),
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


class PrescriptionRenewalController(guava.CallController):
    def __init__(self):
        super().__init__()
        self._patient: dict | None = None
        self._active_meds: list[dict] = []
        self._med_names: list[str] = []

        self.set_persona(
            organization_name="Westfield Medical Group",
            agent_name="Morgan",
            agent_purpose=(
                "to help patients request prescription renewals and submit the renewal to "
                "their care team at Westfield Medical Group for provider review"
            ),
        )

        self.set_task(
            objective=(
                "Collect the patient's name and date of birth to verify their identity, "
                "look up their active medications, confirm which prescription they need renewed, "
                "and submit a renewal request for provider approval."
            ),
            checklist=[
                guava.Say(
                    "Thank you for calling Westfield Medical Group. My name is Morgan and "
                    "I can help you with a prescription renewal request today."
                ),
                guava.Field(
                    key="first_name",
                    field_type="text",
                    description="Ask the caller for their first name.",
                    required=True,
                ),
                guava.Field(
                    key="last_name",
                    field_type="text",
                    description="Ask the caller for their last name.",
                    required=True,
                ),
                guava.Field(
                    key="dob",
                    field_type="text",
                    description=(
                        "Ask the caller for their date of birth to verify their identity. "
                        "Capture it in YYYY-MM-DD format."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="medication_name",
                    field_type="text",
                    description=(
                        "Ask which medication they need renewed. If the name is unclear, "
                        "ask them to spell it out slowly."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="pharmacy_preference",
                    field_type="multiple_choice",
                    description=(
                        "Ask where the patient would like to pick up the renewed prescription: "
                        "their pharmacy already on file, a different pharmacy, or via mail order."
                    ),
                    choices=["pharmacy on file", "different pharmacy", "mail order"],
                    required=True,
                ),
                guava.Field(
                    key="additional_notes",
                    field_type="text",
                    description=(
                        "Ask if there is anything else the patient wants the provider to know when "
                        "reviewing this renewal, such as a change in symptoms or a concern about side effects. "
                        "If they have nothing to add, skip this field."
                    ),
                    required=False,
                ),
            ],
            on_complete=self.process_renewal,
        )

        self.accept_call()

    def process_renewal(self):
        first_name = self.get_field("first_name")
        last_name = self.get_field("last_name")
        dob = self.get_field("dob")
        medication_name = self.get_field("medication_name")
        pharmacy_preference = self.get_field("pharmacy_preference")
        additional_notes = self.get_field("additional_notes")

        # Look up the patient record in Practice Fusion.
        logging.info("Looking up patient: %s %s, DOB %s", first_name, last_name, dob)
        try:
            patient = search_patient(last_name, dob)
        except Exception as exc:
            logging.error("Patient search failed: %s", exc)
            self.hangup(
                final_instructions=(
                    f"Apologize to {first_name} and let them know there was a technical issue "
                    "looking up their record. Ask them to call back during office hours or contact "
                    "Westfield Medical Group directly so a staff member can assist them."
                )
            )
            return

        if patient is None:
            self.hangup(
                final_instructions=(
                    f"Let {first_name} know that no patient record could be found matching the name "
                    f"{first_name} {last_name} and that date of birth. Ask them to double-check the "
                    "information and call back, or to call during office hours so staff can assist."
                )
            )
            return

        patient_id = patient["id"]
        logging.info("Found patient ID: %s", patient_id)

        # Fetch active prescriptions and find the one being renewed.
        try:
            active_meds = get_active_medication_requests(patient_id)
        except Exception as exc:
            logging.error("Failed to fetch active medications for patient %s: %s", patient_id, exc)
            active_meds = []

        name_lower = medication_name.strip().lower()
        matched_med: dict | None = None
        for med in active_meds:
            display = medication_display(med).lower()
            if name_lower in display or display in name_lower:
                matched_med = med
                break

        if matched_med is None:
            self.hangup(
                final_instructions=(
                    f"Let {first_name} know that {medication_name} was not found in their active "
                    "prescriptions on file at Westfield Medical Group. Ask them to call back during "
                    "office hours so a nurse or provider can review their full medication history and "
                    "assist with the renewal."
                )
            )
            return

        matched_name = medication_display(matched_med)
        logging.info("Matched medication: %s", matched_name)

        # Build the note text that will accompany the MedicationRequest renewal proposal.
        note_parts = [
            f"Patient-initiated renewal request via phone.",
            f"Medication requested: {medication_name}.",
            f"Matched active prescription: {matched_name}.",
            f"Pharmacy preference: {pharmacy_preference}.",
        ]
        if additional_notes:
            note_parts.append(f"Patient notes: {additional_notes}")
        note_text = " ".join(note_parts)

        # Post the renewal request to Practice Fusion as a new MedicationRequest.
        try:
            new_request = create_medication_request(patient_id, matched_med, note_text)
            request_id = new_request.get("id", "unknown")
            logging.info("MedicationRequest renewal created: %s", request_id)
        except Exception as exc:
            logging.error("Failed to create MedicationRequest renewal: %s", exc)
            self.hangup(
                final_instructions=(
                    f"Apologize to {first_name} and let them know there was a technical issue "
                    "submitting the renewal request. Ask them to call back during office hours "
                    "or contact the pharmacy directly to initiate the renewal."
                )
            )
            return

        pharmacy_phrase = {
            "pharmacy on file": "their pharmacy on file",
            "different pharmacy": "the pharmacy they specified",
            "mail order": "mail order",
        }.get(pharmacy_preference, pharmacy_preference)

        self.hangup(
            final_instructions=(
                f"Let {first_name} know their renewal request for {matched_name} has been "
                f"submitted successfully and is now pending provider review. Once approved, "
                f"the prescription will be sent to {pharmacy_phrase}. Provider review typically "
                "takes one to two business days. Remind them to call back if they have any "
                "questions, and thank them for choosing Westfield Medical Group."
            )
        )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=PrescriptionRenewalController,
    )

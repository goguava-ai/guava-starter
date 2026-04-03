import guava
import os
import logging
import requests
from datetime import datetime

logging.basicConfig(level=logging.INFO)

CERNER_FHIR_BASE_URL = os.environ["CERNER_FHIR_BASE_URL"]
CERNER_ACCESS_TOKEN = os.environ["CERNER_ACCESS_TOKEN"]

FHIR_HEADERS = {
    "Authorization": f"Bearer {CERNER_ACCESS_TOKEN}",
    "Accept": "application/fhir+json",
    "Content-Type": "application/fhir+json",
}


def find_patient_by_mrn(mrn: str) -> dict | None:
    resp = requests.get(
        f"{CERNER_FHIR_BASE_URL}/Patient",
        headers=FHIR_HEADERS,
        params={"identifier": mrn},
        timeout=10,
    )
    resp.raise_for_status()
    entries = resp.json().get("entry", [])
    return entries[0].get("resource") if entries else None


def get_active_medications(patient_id: str) -> list:
    """Returns active MedicationRequest resources for the patient."""
    resp = requests.get(
        f"{CERNER_FHIR_BASE_URL}/MedicationRequest",
        headers=FHIR_HEADERS,
        params={"patient": patient_id, "status": "active", "_count": 20},
        timeout=10,
    )
    resp.raise_for_status()
    return [e.get("resource") for e in resp.json().get("entry", [])]


def format_medication(med: dict) -> str:
    """Returns a plain-language description of a MedicationRequest."""
    code_text = (
        med.get("medicationCodeableConcept", {}).get("text")
        or med.get("medicationCodeableConcept", {}).get("coding", [{}])[0].get("display")
        or "medication"
    )
    dosage = ""
    dosage_instructions = med.get("dosageInstruction", [{}])
    if dosage_instructions:
        dosage = dosage_instructions[0].get("text", "")
    return f"{code_text}" + (f" ({dosage})" if dosage else "")


def create_service_request(patient_id: str, medication_name: str, pharmacy: str, notes: str) -> str:
    """Creates a FHIR ServiceRequest for a medication refill. Returns the request ID."""
    resource = {
        "resourceType": "ServiceRequest",
        "status": "active",
        "intent": "order",
        "category": [
            {
                "coding": [
                    {
                        "system": "http://snomed.info/sct",
                        "code": "103696004",
                        "display": "Patient referral to pharmacy",
                    }
                ]
            }
        ],
        "code": {
            "text": f"Medication refill request: {medication_name}",
        },
        "subject": {"reference": f"Patient/{patient_id}"},
        "note": [{"text": notes}],
        "occurrenceDateTime": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "patientInstruction": f"Preferred pharmacy: {pharmacy}" if pharmacy else "",
    }
    resp = requests.post(
        f"{CERNER_FHIR_BASE_URL}/ServiceRequest",
        headers=FHIR_HEADERS,
        json=resource,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("id", "")


class MedicationRefillController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Riverside Health System",
            agent_name="Sam",
            agent_purpose=(
                "to help Riverside Health System patients request prescription refills "
                "without needing to wait on hold or visit the clinic"
            ),
        )

        self.set_task(
            objective=(
                "A patient has called to request a prescription refill. Verify their identity, "
                "identify which medication they need refilled, and submit the refill request "
                "through the EHR."
            ),
            checklist=[
                guava.Say(
                    "Thank you for calling Riverside Health System. I'm Sam, and I can help "
                    "you request a prescription refill. Let me pull up your record."
                ),
                guava.Field(
                    key="mrn",
                    field_type="text",
                    description="Ask for their medical record number (MRN).",
                    required=True,
                ),
                guava.Field(
                    key="date_of_birth",
                    field_type="text",
                    description="Ask for their date of birth to verify identity. Repeat it back.",
                    required=True,
                ),
                guava.Field(
                    key="medication_name",
                    field_type="text",
                    description=(
                        "Ask which medication they need refilled. "
                        "Capture the name as they describe it — it doesn't need to be the exact clinical name."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="preferred_pharmacy",
                    field_type="text",
                    description=(
                        "Ask which pharmacy they'd like the refill sent to. "
                        "Confirm the pharmacy name and location."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="urgency",
                    field_type="multiple_choice",
                    description=(
                        "Ask how soon they need the refill."
                    ),
                    choices=["today — I'm almost out", "within a few days", "no rush"],
                    required=True,
                ),
                guava.Field(
                    key="side_effects",
                    field_type="multiple_choice",
                    description=(
                        "Ask if they've experienced any side effects or concerns with this medication "
                        "since their last prescription."
                    ),
                    choices=["no issues", "yes, I have a concern"],
                    required=True,
                ),
                guava.Field(
                    key="side_effect_detail",
                    field_type="text",
                    description=(
                        "If they have a concern, ask them to describe it. "
                        "Capture the full detail — this will be flagged for the provider."
                    ),
                    required=False,
                ),
            ],
            on_complete=self.submit_refill_request,
        )

        self.accept_call()

    def submit_refill_request(self):
        mrn = (self.get_field("mrn") or "").strip()
        dob = self.get_field("date_of_birth") or ""
        medication = self.get_field("medication_name") or ""
        pharmacy = self.get_field("preferred_pharmacy") or ""
        urgency = self.get_field("urgency") or "within a few days"
        side_effects = self.get_field("side_effects") or "no issues"
        side_effect_detail = self.get_field("side_effect_detail") or ""

        logging.info("Looking up patient by MRN: %s", mrn)
        patient = None
        try:
            patient = find_patient_by_mrn(mrn)
        except Exception as e:
            logging.error("Patient lookup failed: %s", e)

        if not patient:
            self.hangup(
                final_instructions=(
                    "Let the caller know you couldn't locate their record with that MRN and date of birth. "
                    "Ask them to double-check the MRN or offer to transfer them to the front desk."
                )
            )
            return

        patient_id = patient.get("id", "")
        name_entry = (patient.get("name") or [{}])[0]
        given = " ".join(name_entry.get("given", []))
        family = name_entry.get("family", "")
        patient_name = f"{given} {family}".strip() or "the patient"

        notes = (
            f"Refill requested for: {medication}\n"
            f"Preferred pharmacy: {pharmacy}\n"
            f"Urgency: {urgency}\n"
            f"Side effects reported: {side_effects}"
        )
        if side_effect_detail:
            notes += f"\nSide effect detail: {side_effect_detail}"

        has_concern = side_effects == "yes, I have a concern"

        logging.info(
            "Submitting refill request for patient %s — medication: %s, urgency: %s",
            patient_id, medication, urgency,
        )
        request_id = ""
        try:
            request_id = create_service_request(patient_id, medication, pharmacy, notes)
            logging.info("FHIR ServiceRequest created: %s", request_id)
        except Exception as e:
            logging.error("Failed to create FHIR ServiceRequest: %s", e)

        if has_concern:
            self.hangup(
                final_instructions=(
                    f"Let {patient_name} know their refill request has been submitted but that "
                    "their concern about side effects has been flagged for the provider to review. "
                    "Let them know the provider's office will contact them before sending the refill. "
                    + (f"Reference ID: {request_id}. " if request_id else "")
                    + "Thank them for mentioning the concern and wish them good health."
                )
            )
        elif request_id:
            sla = {
                "today — I'm almost out": "within a few hours",
                "within a few days": "within 1–2 business days",
                "no rush": "within 2–3 business days",
            }.get(urgency, "shortly")

            self.hangup(
                final_instructions=(
                    f"Let {patient_name} know their refill request for {medication} has been submitted. "
                    f"It should be sent to {pharmacy} {sla}. "
                    + (f"Reference ID: {request_id}. " if request_id else "")
                    + "Thank them for calling Riverside Health System and wish them good health."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    f"Apologize to {patient_name} for a technical issue. Ask them to contact "
                    "the pharmacy directly or call back to resubmit. Thank them for their patience."
                )
            )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=MedicationRefillController,
    )

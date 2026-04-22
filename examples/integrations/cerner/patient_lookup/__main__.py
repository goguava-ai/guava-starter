import guava
import os
import logging
import requests
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)

CERNER_FHIR_BASE_URL = os.environ["CERNER_FHIR_BASE_URL"]  # e.g. https://fhir-ehr-code.cerner.com/r4/...
CERNER_ACCESS_TOKEN = os.environ["CERNER_ACCESS_TOKEN"]

FHIR_HEADERS = {
    "Authorization": f"Bearer {CERNER_ACCESS_TOKEN}",
    "Accept": "application/fhir+json",
}


def find_patient_by_mrn(mrn: str) -> dict | None:
    """Searches for a FHIR Patient by MRN (medical record number). Returns the Patient resource or None."""
    resp = requests.get(
        f"{CERNER_FHIR_BASE_URL}/Patient",
        headers=FHIR_HEADERS,
        params={"identifier": mrn},
        timeout=10,
    )
    resp.raise_for_status()
    bundle = resp.json()
    entries = bundle.get("entry", [])
    return entries[0].get("resource") if entries else None


def find_patient_by_name_dob(family: str, given: str, dob: str) -> dict | None:
    """Searches for a FHIR Patient by name and date of birth."""
    resp = requests.get(
        f"{CERNER_FHIR_BASE_URL}/Patient",
        headers=FHIR_HEADERS,
        params={"family": family, "given": given, "birthdate": dob},
        timeout=10,
    )
    resp.raise_for_status()
    entries = resp.json().get("entry", [])
    return entries[0].get("resource") if entries else None


def get_upcoming_appointments(patient_id: str) -> list:
    """Returns upcoming Appointments for a patient."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    resp = requests.get(
        f"{CERNER_FHIR_BASE_URL}/Appointment",
        headers=FHIR_HEADERS,
        params={"patient": patient_id, "date": f"ge{today}", "_count": 5},
        timeout=10,
    )
    resp.raise_for_status()
    return [e.get("resource") for e in resp.json().get("entry", [])]


def parse_patient_summary(patient: dict) -> dict:
    """Extracts key fields from a FHIR Patient resource."""
    name_entry = (patient.get("name") or [{}])[0]
    given = " ".join(name_entry.get("given", []))
    family = name_entry.get("family", "")
    full_name = f"{given} {family}".strip()

    dob = patient.get("birthDate", "")
    gender = patient.get("gender", "")
    mrn = ""
    for identifier in patient.get("identifier", []):
        if identifier.get("type", {}).get("text", "") == "MRN" or "MR" in str(identifier.get("type", {})):
            mrn = identifier.get("value", "")
            break

    telecom = patient.get("telecom", [])
    phone = next((t.get("value") for t in telecom if t.get("system") == "phone"), "")

    return {
        "id": patient.get("id", ""),
        "name": full_name,
        "dob": dob,
        "gender": gender,
        "mrn": mrn,
        "phone": phone,
    }


class PatientLookupController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Riverside Health System",
            agent_name="Sam",
            agent_purpose=(
                "to assist Riverside Health System patients with account inquiries, including "
                "appointment information and general account questions"
            ),
        )

        self.set_task(
            objective=(
                "A patient has called Riverside Health System. Verify their identity, look up "
                "their record in the EHR, and assist them with their inquiry."
            ),
            checklist=[
                guava.Say(
                    "Thank you for calling Riverside Health System. I'm Sam. "
                    "I'll look up your record — may I start with your date of birth "
                    "and last name to verify your identity?"
                ),
                guava.Field(
                    key="last_name",
                    field_type="text",
                    description="Ask for their last name.",
                    required=True,
                ),
                guava.Field(
                    key="first_name",
                    field_type="text",
                    description="Ask for their first name.",
                    required=True,
                ),
                guava.Field(
                    key="date_of_birth",
                    field_type="text",
                    description=(
                        "Ask for their date of birth. Confirm it back in full (e.g. 'January 15, 1982')."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="mrn",
                    field_type="text",
                    description=(
                        "Ask if they have their medical record number (MRN) handy. "
                        "Let them know it's on their patient portal or paperwork. Skip if they don't have it."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="reason_for_call",
                    field_type="multiple_choice",
                    description="Ask what they're calling about today.",
                    choices=[
                        "appointment question",
                        "medical records request",
                        "billing question",
                        "prescription question",
                        "general question",
                    ],
                    required=True,
                ),
            ],
            on_complete=self.lookup_patient,
        )

        self.accept_call()

    def lookup_patient(self):
        last_name = self.get_field("last_name") or ""
        first_name = self.get_field("first_name") or ""
        dob = self.get_field("date_of_birth") or ""
        mrn = (self.get_field("mrn") or "").strip()
        reason = self.get_field("reason_for_call") or "general question"

        patient = None
        try:
            if mrn:
                logging.info("Looking up patient by MRN: %s", mrn)
                patient = find_patient_by_mrn(mrn)
            if not patient:
                logging.info("Looking up patient by name/DOB: %s %s, %s", first_name, last_name, dob)
                patient = find_patient_by_name_dob(last_name, first_name, dob)
        except Exception as e:
            logging.error("FHIR patient lookup failed: %s", e)

        if not patient:
            self.hangup(
                final_instructions=(
                    f"Let the caller know you were unable to locate a patient record matching "
                    f"{first_name} {last_name} with that date of birth. Ask them to verify the "
                    "spelling or their date of birth, or offer to transfer them to the patient "
                    "services team. Be empathetic and patient."
                )
            )
            return

        summary = parse_patient_summary(patient)
        patient_id = summary["id"]
        name = summary["name"] or f"{first_name} {last_name}"

        logging.info("Patient found: %s (ID: %s)", name, patient_id)

        appt_context = ""
        if reason == "appointment question" and patient_id:
            try:
                appts = get_upcoming_appointments(patient_id)
                if appts:
                    appt_lines = []
                    for a in appts[:3]:
                        start = a.get("start", "")[:10]
                        appt_type = a.get("appointmentType", {}).get("text", "appointment")
                        status = a.get("status", "")
                        appt_lines.append(f"{appt_type} on {start} ({status})")
                    appt_context = "Upcoming appointments: " + "; ".join(appt_lines)
                else:
                    appt_context = "No upcoming appointments found in the system."
            except Exception as e:
                logging.error("Failed to fetch appointments for patient %s: %s", patient_id, e)

        self.hangup(
            final_instructions=(
                f"Greet {name} by name — do not reveal sensitive medical details unprompted. "
                f"Their record was found. Reason for call: {reason}. "
                + (f"Appointment info: {appt_context} " if appt_context else "")
                + "Assist them with their question professionally. For medical records, direct them "
                "to the records department. For billing, to the billing team. "
                "Thank them for calling Riverside Health System."
            )
        )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=PatientLookupController,
    )

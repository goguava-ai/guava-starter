import guava
import os
import logging
from guava import logging_utils
import requests


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


def log_call(patient_id: int, notes: str) -> dict:
    """Log a call record (used here to document the refill request)."""
    resp = requests.post(
        f"{BASE_URL}/call_logs",
        headers=HEADERS,
        json={
            "patient": patient_id,
            "notes": notes,
            "called_by": DOCTOR_ID,
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


agent = guava.Agent(
    name="Morgan",
    organization="Oakridge Family Medicine",
    purpose=(
        "to help patients submit prescription refill requests to the care team "
        "at Oakridge Family Medicine"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "handle_complete",
        objective=(
            "A patient has called Oakridge Family Medicine to request a prescription refill. "
            "Verify their identity, collect the refill details, and route the request to the care team."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling Oakridge Family Medicine. "
                "My name is Morgan. I can help you submit a prescription refill request today."
            ),
            guava.Field(
                key="patient_email",
                field_type="text",
                description="Ask for the caller's email address to look up their patient record.",
                required=True,
            ),
            guava.Field(
                key="date_of_birth",
                field_type="text",
                description=(
                    "Ask for their date of birth to verify their identity. "
                    "Capture in YYYY-MM-DD format."
                ),
                required=True,
            ),
            guava.Field(
                key="medication_name",
                field_type="text",
                description=(
                    "Ask which medication they need refilled. "
                    "Capture the medication name and dosage if they know it, for example 'Lisinopril 10mg'."
                ),
                required=True,
            ),
            guava.Field(
                key="pharmacy_name",
                field_type="text",
                description=(
                    "Ask which pharmacy they'd like the prescription sent to. "
                    "Capture the pharmacy name and location."
                ),
                required=True,
            ),
            guava.Field(
                key="pharmacy_phone",
                field_type="text",
                description=(
                    "Ask for the pharmacy phone number if they have it handy. "
                    "This is optional — skip if they don't know it."
                ),
                required=False,
            ),
            guava.Field(
                key="has_changed_medications",
                field_type="multiple_choice",
                description=(
                    "Ask if they have started or stopped any other medications since their last visit."
                ),
                choices=["yes", "no"],
                required=True,
            ),
        ],
    )


@agent.on_task_complete("handle_complete")
def on_handle_complete(call: guava.Call) -> None:
    email = call.get_field("patient_email") or ""
    dob = call.get_field("date_of_birth") or ""
    medication = call.get_field("medication_name") or "medication"
    pharmacy = call.get_field("pharmacy_name") or "patient's preferred pharmacy"
    pharmacy_phone = call.get_field("pharmacy_phone") or ""
    has_changed_medications = call.get_field("has_changed_medications") or "no"

    # Look up patient by email
    patient = None
    patient_id = None
    patient_first = "the patient"
    try:
        patient = search_patient_by_email(email)
        if patient:
            patient_id = patient["id"]
            patient_first = patient.get("first_name", "the patient")
            stored_dob = patient.get("date_of_birth", "")
            logging.info(
                "Found patient %s (ID: %s), DOB on file: %s, provided: %s",
                patient_first, patient_id, stored_dob, dob,
            )
        else:
            logging.warning("No patient found with email: %s", email)
    except Exception as e:
        logging.error("Patient lookup failed: %s", e)

    if not patient_id:
        call.hangup(
            final_instructions=(
                "Let the caller know we were unable to locate their patient record with the email provided. "
                "Ask them to call back and have their patient ID or registration information ready, "
                "or offer to transfer them to the front desk. Apologize for the inconvenience."
            )
        )
        return

    # Build refill request notes
    pharmacy_detail = pharmacy
    if pharmacy_phone:
        pharmacy_detail += f" (phone: {pharmacy_phone})"

    medication_change_note = (
        " Patient reported changes to other medications since last visit — care team should review."
        if has_changed_medications == "yes"
        else ""
    )

    notes = (
        f"Prescription refill request from {patient_first}. "
        f"Medication: {medication}. "
        f"Preferred pharmacy: {pharmacy_detail}."
        f"{medication_change_note}"
    )

    logged = False
    try:
        log_call(patient_id, notes)
        logged = True
        logging.info(
            "Refill request logged for patient %s: %s → %s",
            patient_id, medication, pharmacy,
        )
    except Exception as e:
        logging.error("Failed to log refill request for patient %s: %s", patient_id, e)

    if logged:
        call.hangup(
            final_instructions=(
                f"Let {patient_first} know their refill request for {medication} has been sent to "
                "the care team at Oakridge Family Medicine. "
                "Tell them the team will review and send it to their pharmacy within one to two business days. "
                + (
                    "Let them know a care team member may follow up regarding the medication changes they mentioned. "
                    if has_changed_medications == "yes"
                    else ""
                )
                + "Thank them for calling and wish them a great day."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Apologize to {patient_first} and let them know there was a technical issue submitting "
                "the refill request. Ask them to call back or assure them a team member will follow up. "
                "Thank them for their patience."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])

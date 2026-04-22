import logging
import os

import guava
import requests
from guava import logging_utils

BASE_URL = os.environ["PRACTICE_FUSION_FHIR_BASE_URL"]  # e.g. https://api.practicefusion.com/fhir/r4


def get_headers():
    return {
        "Authorization": f"Bearer {os.environ['PRACTICE_FUSION_ACCESS_TOKEN']}",
        "Content-Type": "application/json",
    }


def search_patient(last_name: str, dob: str) -> dict | None:
    """Search for a patient by last name and date of birth. Returns the first matching patient resource or None."""
    url = f"{BASE_URL}/Patient"
    params = {"family": last_name, "birthdate": dob}
    response = requests.get(url, headers=get_headers(), params=params)
    response.raise_for_status()
    bundle = response.json()
    entries = bundle.get("entry", [])
    if not entries:
        return None
    return entries[0]["resource"]


def get_active_medications(patient_id: str) -> list[dict]:
    """Return a list of active MedicationRequest resources for the given patient."""
    url = f"{BASE_URL}/MedicationRequest"
    params = {"patient": f"Patient/{patient_id}", "status": "active"}
    response = requests.get(url, headers=get_headers(), params=params)
    response.raise_for_status()
    bundle = response.json()
    return [entry["resource"] for entry in bundle.get("entry", [])]


def find_matching_medication(medications: list[dict], medication_name: str) -> dict | None:
    """Find the first medication whose display name contains the requested medication name (case-insensitive)."""
    name_lower = medication_name.lower()
    for med in medications:
        coding = (
            med.get("medicationCodeableConcept", {})
            .get("coding", [])
        )
        text = med.get("medicationCodeableConcept", {}).get("text", "")
        display_values = [c.get("display", "") for c in coding] + [text]
        for display in display_values:
            if name_lower in display.lower():
                return med
    return None


def create_refill_request(patient_id: str, medication: dict, pharmacy_preference: str) -> dict:
    """POST a new MedicationRequest with intent='plan' to represent a refill request."""
    medication_codeable_concept = medication.get("medicationCodeableConcept", {})
    requester = medication.get("requester", {"display": "Riverside Family Medicine"})

    note_text = f"Patient-requested refill. Pharmacy preference: {pharmacy_preference}."

    refill_resource = {
        "resourceType": "MedicationRequest",
        "status": "active",
        "intent": "plan",
        "subject": {"reference": f"Patient/{patient_id}"},
        "medicationCodeableConcept": medication_codeable_concept,
        "requester": requester,
        "note": [{"text": note_text}],
    }

    url = f"{BASE_URL}/MedicationRequest"
    response = requests.post(url, headers=get_headers(), json=refill_resource)
    response.raise_for_status()
    return response.json()


agent = guava.Agent(
    name="Alex",
    organization="Riverside Family Medicine",
    purpose="to help patients request prescription refills",
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "process_refill",
        objective=(
            "Collect the patient's information and the medication they need refilled, "
            "verify the prescription against their active medications, submit the refill "
            "request, and let them know the expected timeline."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling Riverside Family Medicine. My name is Alex "
                "and I can help you with a prescription refill request today."
            ),
            guava.Field(
                key="first_name",
                field_type="text",
                description="Ask the patient for their first name.",
                required=True,
            ),
            guava.Field(
                key="last_name",
                field_type="text",
                description="Ask the patient for their last name.",
                required=True,
            ),
            guava.Field(
                key="dob",
                field_type="text",
                description=(
                    "Ask the patient for their date of birth for verification purposes. "
                    "Capture it in YYYY-MM-DD format."
                ),
                required=True,
            ),
            guava.Field(
                key="medication_name",
                field_type="text",
                description=(
                    "Ask which medication they need refilled. Have them spell it out if "
                    "the name is unclear."
                ),
                required=True,
            ),
            guava.Field(
                key="pharmacy_preference",
                field_type="multiple_choice",
                description=(
                    "Ask where they would like to pick up their refill: their pharmacy "
                    "on file, a different pharmacy, or mail order."
                ),
                choices=["same pharmacy on file", "different pharmacy", "mail order"],
                required=True,
            ),
        ],
    )


@agent.on_task_complete("process_refill")
def on_done(call: guava.Call) -> None:
    first_name = call.get_field("first_name")
    last_name = call.get_field("last_name")
    dob = call.get_field("dob")
    medication_name = call.get_field("medication_name")
    pharmacy_preference = call.get_field("pharmacy_preference")

    logging.info("Looking up patient: %s %s, DOB %s", first_name, last_name, dob)
    patient = search_patient(last_name, dob)

    if patient is None:
        call.hangup(
            final_instructions=(
                f"Apologize and let the patient know you were unable to locate a record "
                f"for {first_name} {last_name} with that date of birth. Ask them to call "
                "back during office hours so a staff member can assist them directly."
            )
        )
        return

    patient_id = patient["id"]
    logging.info("Found patient ID: %s", patient_id)

    logging.info("Fetching active medications for patient %s", patient_id)
    active_medications = get_active_medications(patient_id)

    matched_medication = find_matching_medication(active_medications, medication_name)

    if matched_medication is None:
        call.hangup(
            final_instructions=(
                f"Let {first_name} know that {medication_name} was not found among their "
                "active prescriptions on file. Ask them to call back during office hours "
                "so a nurse or provider can review their medication history and assist with "
                "the refill."
            )
        )
        return

    logging.info("Matched medication: %s", matched_medication.get("medicationCodeableConcept", {}))

    try:
        refill = create_refill_request(patient_id, matched_medication, pharmacy_preference)
        refill_id = refill.get("id", "unknown")
        logging.info("Refill request created with ID: %s", refill_id)

        pharmacy_message = {
            "same pharmacy on file": "your pharmacy on file",
            "different pharmacy": "the new pharmacy you specified",
            "mail order": "mail order",
        }.get(pharmacy_preference, pharmacy_preference)

        call.hangup(
            final_instructions=(
                f"Let {first_name} know their refill request for {medication_name} has been "
                f"submitted successfully. The request number is {refill_id}. The prescription "
                f"will be sent to {pharmacy_message} once a provider reviews and approves it, "
                "which typically takes one to two business days. Thank them for calling "
                "Riverside Family Medicine and wish them well."
            )
        )
    except requests.HTTPError as exc:
        logging.error("Failed to create refill request: %s", exc)
        call.hangup(
            final_instructions=(
                f"Apologize to {first_name} and let them know there was a technical issue "
                "submitting the refill request. Ask them to call back during office hours "
                "or contact their pharmacy directly to initiate the refill."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])

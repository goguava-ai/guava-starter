import argparse
import logging
import os

import guava
import requests
from guava import logging_utils


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


agent = guava.Agent(
    name="Sam",
    organization="Sunrise Family Practice",
    purpose="to complete pre-visit intake for patients before their appointments",
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")
    patient_id = call.get_variable("patient_id")
    appointment_time = call.get_variable("appointment_time")

    headers = {}
    existing_meds: list = []
    existing_allergies: list = []

    try:
        token = get_access_token()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        existing_meds = get_medications(patient_id, headers)
        existing_allergies = get_allergies(patient_id, headers)
        logging.info(
            "Pre-call data: patient=%s, meds=%d, allergies=%d",
            patient_id, len(existing_meds), len(existing_allergies),
        )
    except Exception as e:
        logging.error("Failed to load pre-call data for patient %s: %s", patient_id, e)

    call.set_variable("headers", headers)

    med_names = []
    for e in existing_meds:
        r = e.get("resource", {})
        med = r.get("medicationCodeableConcept", {}).get("text", "") or r.get("medicationReference", {}).get("display", "")
        if med:
            med_names.append(med)

    allergy_names = []
    for e in existing_allergies:
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

    call.set_variable("meds_context", meds_context)
    call.set_variable("allergies_context", allergies_context)

    call.reach_person(contact_full_name=patient_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    patient_name = call.get_variable("patient_name")
    appointment_time = call.get_variable("appointment_time")
    if outcome == "unavailable":
        logging.info("Unable to reach %s for intake.", patient_name)
        call.hangup(
            final_instructions=(
                f"Leave a brief voicemail for {patient_name} from Sunrise Family Practice "
                f"asking them to call back for a quick pre-visit check-in before their "
                f"appointment on {appointment_time}."
            )
        )
    elif outcome == "available":
        call.set_task(
            "patient_intake",
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
                    description=call.get_variable("meds_context"),
                    required=True,
                ),
                guava.Field(
                    key="allergies",
                    field_type="text",
                    description=call.get_variable("allergies_context"),
                    required=True,
                ),
                guava.Field(
                    key="recent_changes",
                    field_type="text",
                    description="Ask about any significant health changes since their last visit.",
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("patient_intake")
def on_done(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")
    patient_id = call.get_variable("patient_id")
    appointment_time = call.get_variable("appointment_time")
    complaint = call.get_field("chief_complaint") or ""
    meds = call.get_field("medications") or ""
    allergies = call.get_field("allergies") or ""
    changes = call.get_field("recent_changes") or "None reported"

    note = (
        f"Pre-Visit Intake — {appointment_time}\n"
        f"Chief complaint: {complaint}\n"
        f"Current medications: {meds}\n"
        f"Allergies: {allergies}\n"
        f"Recent changes: {changes}"
    )
    logging.info("Intake for patient %s:\n%s", patient_id, note)

    try:
        posted = post_document_reference(patient_id, note, call.get_variable("headers"))
        logging.info("Intake DocumentReference posted: %s", posted)
    except Exception as e:
        logging.error("Failed to post intake document: %s", e)

    call.hangup(
        final_instructions=(
            f"Thank {patient_name} for completing intake. Let them know the care team "
            "will review their information before the visit. Remind them to arrive 10 minutes "
            "early with their insurance card. Wish them a great day."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(description="Outbound patient intake via eClinicalWorks FHIR.")
    parser.add_argument("phone", help="Patient phone number (E.164)")
    parser.add_argument("--name", required=True)
    parser.add_argument("--patient-id", required=True)
    parser.add_argument("--appointment", required=True, help="Appointment date/time display string")
    args = parser.parse_args()

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "patient_name": args.name,
            "patient_id": args.patient_id,
            "appointment_time": args.appointment,
        },
    )

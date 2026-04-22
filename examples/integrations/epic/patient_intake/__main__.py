import guava
import os
import logging
from guava import logging_utils
import json
import requests
import argparse
from datetime import datetime, timezone


agent = guava.Agent(
    name="Maya",
    organization="Cedar Health",
    purpose=(
        "to complete pre-visit intake for patients before their upcoming appointment, "
        "confirming or updating their medications and allergies on file and collecting "
        "their chief complaint"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")
    patient_id = call.get_variable("patient_id")

    known_allergies = []
    known_medications = []

    # Pre-call: fetch the patient's current allergies and medications from Epic.
    # Having these on hand lets the agent confirm existing records rather than
    # making the patient recite everything from scratch — a much better experience.
    try:
        base_url = os.environ["EPIC_BASE_URL"]
        access_token = os.environ["EPIC_ACCESS_TOKEN"]
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        allergy_resp = requests.get(
            f"{base_url}/AllergyIntolerance",
            headers=headers,
            params={"patient": patient_id, "clinical-status": "active"},
            timeout=10,
        )
        allergy_resp.raise_for_status()
        for entry in allergy_resp.json().get("entry", []):
            resource = entry.get("resource", {})
            substance = (
                resource.get("code", {}).get("text")
                or next((c.get("display") for c in resource.get("code", {}).get("coding", []) if c.get("display")), None)
            )
            if substance:
                known_allergies.append(substance)
        logging.info("Fetched %d allergy record(s) from Epic for patient %s", len(known_allergies), patient_id)
    except Exception as e:
        logging.error("Failed to fetch Epic AllergyIntolerance: %s", e)

    try:
        base_url = os.environ["EPIC_BASE_URL"]
        access_token = os.environ["EPIC_ACCESS_TOKEN"]
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        med_resp = requests.get(
            f"{base_url}/MedicationStatement",
            headers=headers,
            params={"patient": patient_id, "status": "active"},
            timeout=10,
        )
        med_resp.raise_for_status()
        for entry in med_resp.json().get("entry", []):
            resource = entry.get("resource", {})
            med_name = (
                resource.get("medicationCodeableConcept", {}).get("text")
                or next(
                    (c.get("display") for c in resource.get("medicationCodeableConcept", {}).get("coding", []) if c.get("display")),
                    None,
                )
            )
            if med_name:
                known_medications.append(med_name)
        logging.info("Fetched %d medication record(s) from Epic for patient %s", len(known_medications), patient_id)
    except Exception as e:
        logging.error("Failed to fetch Epic MedicationStatement: %s", e)

    call.set_variable("known_allergies", known_allergies)
    call.set_variable("known_medications", known_medications)

    call.reach_person(contact_full_name=patient_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    patient_name = call.get_variable("patient_name")
    appointment = call.get_variable("appointment")
    if outcome == "unavailable":
        call.hangup(
            final_instructions=(
                "We were unable to reach the patient. Leave a brief voicemail on behalf of Cedar Health "
                "asking them to call back to complete their pre-visit intake before their upcoming appointment."
            )
        )
    elif outcome == "available":
        # Dynamically build the question descriptions based on what Epic already has on file.
        # If records exist, the agent reads them back for confirmation; otherwise asks from scratch.
        known_medications = call.get_variable("known_medications") or []
        known_allergies = call.get_variable("known_allergies") or []
        if known_medications:
            med_list = ", ".join(known_medications)
            medications_description = (
                f"We currently have the following medications on file for this patient: {med_list}. "
                "Read this list back to the patient and ask whether it is still accurate, or if "
                "anything has been added, changed, or stopped. Capture their confirmation or the full "
                "updated list."
            )
        else:
            medications_description = (
                "Ask the patient to list any medications they are currently taking, "
                "including prescription drugs, over-the-counter medications, and supplements. "
                "If none, capture 'none'."
            )

        if known_allergies:
            allergy_list = ", ".join(known_allergies)
            allergies_description = (
                f"We currently have the following allergies on file for this patient: {allergy_list}. "
                "Read this list back to the patient and ask whether it is still accurate, or if "
                "anything has been added or removed. Capture their confirmation or the updated list."
            )
        else:
            allergies_description = (
                "Ask the patient if they have any known allergies to medications, foods, "
                "or environmental factors. If none, capture 'none'."
            )

        call.set_task(
            "patient_intake",
            objective=(
                f"Complete a pre-visit intake with {patient_name} before their appointment "
                f"at Cedar Health on {appointment}. Collect their chief complaint, confirm or "
                "update medications and allergies on file, and note any recent health changes."
            ),
            checklist=[
                guava.Say(
                    f"Hi {patient_name}, this is Maya calling from Cedar Health. "
                    f"I'm calling to complete a quick pre-visit intake before your appointment "
                    f"on {appointment}. This will help your care team prepare for your visit."
                ),
                guava.Field(
                    key="chief_complaint",
                    description=(
                        "Ask the patient what is the main reason for their upcoming visit — "
                        "what symptom or concern they would most like to address."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="current_medications",
                    description=medications_description,
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="allergies",
                    description=allergies_description,
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="recent_health_changes",
                    description=(
                        "Ask if the patient has experienced any significant health changes recently, "
                        "such as new symptoms, hospitalizations, or changes to existing conditions. "
                        "Skip if nothing new to report."
                    ),
                    field_type="text",
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("patient_intake")
def on_done(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")
    patient_id = call.get_variable("patient_id")
    appointment = call.get_variable("appointment")

    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": "Maya",
        "organization": "Cedar Health",
        "use_case": "patient_intake",
        "patient_name": patient_name,
        "patient_id": patient_id,
        "prior_record": {
            "medications_on_file": call.get_variable("known_medications"),
            "allergies_on_file": call.get_variable("known_allergies"),
        },
        "fields": {
            "chief_complaint": call.get_field("chief_complaint"),
            "current_medications": call.get_field("current_medications"),
            "allergies": call.get_field("allergies"),
            "recent_health_changes": call.get_field("recent_health_changes"),
        },
    }
    print(json.dumps(results, indent=2))
    logging.info("Patient intake results saved locally.")

    # Post-call: upload the full intake summary to Epic as a DocumentReference
    # (LOINC 34117-2: History and Physical Note) so the care team can review it
    # in the patient's chart before the appointment.
    try:
        base_url = os.environ["EPIC_BASE_URL"]
        access_token = os.environ["EPIC_ACCESS_TOKEN"]
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        note_text = (
            f"Pre-visit intake for {patient_name} — {appointment}\n"
            f"Chief complaint: {call.get_field('chief_complaint')}\n"
            f"Medications (patient-confirmed): {call.get_field('current_medications')}\n"
            f"Allergies (patient-confirmed): {call.get_field('allergies')}\n"
            f"Recent changes: {call.get_field('recent_health_changes') or 'None reported'}"
        )
        import base64
        encoded_note = base64.b64encode(note_text.encode()).decode()

        doc_payload = {
            "resourceType": "DocumentReference",
            "status": "current",
            "type": {
                "coding": [{"system": "http://loinc.org", "code": "34117-2", "display": "History and physical note"}]
            },
            "subject": {"reference": f"Patient/{patient_id}"},
            "date": datetime.now(timezone.utc).isoformat(),
            "content": [
                {
                    "attachment": {
                        "contentType": "text/plain",
                        "data": encoded_note,
                        "title": f"Pre-visit intake — {patient_name}",
                    }
                }
            ],
        }

        resp = requests.post(
            f"{base_url}/DocumentReference",
            headers=headers,
            json=doc_payload,
            timeout=10,
        )
        resp.raise_for_status()
        doc_id = resp.json().get("id", "")
        logging.info("Epic DocumentReference created: %s", doc_id)
    except Exception as e:
        logging.error("Failed to create Epic DocumentReference: %s", e)

    call.hangup(
        final_instructions=(
            f"Thank {patient_name} for completing the pre-visit intake. Let them know "
            "their responses have been shared with their care team at Cedar Health and will be "
            f"reviewed before their appointment on {appointment}. Remind them to arrive "
            "10 minutes early and wish them a great day."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound pre-visit patient intake call for Cedar Health via Epic FHIR."
    )
    parser.add_argument("phone", help="Patient phone number to call (E.164 format, e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Full name of the patient")
    parser.add_argument("--patient-id", required=True, help="Epic Patient FHIR resource ID")
    parser.add_argument(
        "--appointment",
        default="tomorrow at 9:00 AM",
        help="Appointment datetime string shown to the patient (default: 'tomorrow at 9:00 AM')",
    )
    args = parser.parse_args()

    logging.info(
        "Initiating patient intake call to %s (%s), patient ID: %s",
        args.name,
        args.phone,
        args.patient_id,
    )

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "patient_name": args.name,
            "patient_id": args.patient_id,
            "appointment": args.appointment,
        },
    )

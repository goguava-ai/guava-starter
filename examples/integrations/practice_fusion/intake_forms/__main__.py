import base64
import guava
import os
import logging
from guava import logging_utils
import argparse
import requests
from datetime import datetime, timezone


BASE_URL = os.environ.get("PRACTICE_FUSION_FHIR_BASE_URL", "https://api.practicefusion.com/fhir/r4")


def get_headers():
    return {
        "Authorization": f"Bearer {os.environ['PRACTICE_FUSION_ACCESS_TOKEN']}",
        "Content-Type": "application/json",
    }


def create_document_reference(patient_id: str, note_text: str, appointment_date: str) -> dict:
    """
    POST a DocumentReference to Practice Fusion containing the intake form responses.
    Uses LOINC 34117-2 (History and Physical Note) as the document type.
    Content is base64-encoded plain text.
    """
    encoded = base64.b64encode(note_text.encode("utf-8")).decode("utf-8")
    payload = {
        "resourceType": "DocumentReference",
        "status": "current",
        "type": {
            "coding": [
                {
                    "system": "http://loinc.org",
                    "code": "34117-2",
                    "display": "History and physical note",
                }
            ]
        },
        "subject": {"reference": f"Patient/{patient_id}"},
        "date": datetime.now(timezone.utc).isoformat(),
        "description": f"Pre-visit intake — {appointment_date}",
        "content": [
            {
                "attachment": {
                    "contentType": "text/plain",
                    "data": encoded,
                    "title": f"Pre-visit intake — {appointment_date}",
                }
            }
        ],
    }
    resp = requests.post(
        f"{BASE_URL}/DocumentReference",
        headers=get_headers(),
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


agent = guava.Agent(
    name="Jamie",
    organization="Sunrise Family Practice",
    purpose=(
        "to complete a pre-visit intake with patients before their appointment at "
        "Sunrise Family Practice so their care team can prepare in advance"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")
    call.reach_person(contact_full_name=patient_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    patient_name = call.get_variable("patient_name")
    appointment_date = call.get_variable("appointment_date")

    if outcome == "unavailable":
        call.hangup(
            final_instructions=(
                f"Leave a brief voicemail for {patient_name} on behalf of Sunrise Family Practice. "
                "Let them know we called to complete a quick pre-visit intake before their upcoming "
                "appointment and ask them to call us back at their earliest convenience. "
                "Keep it brief and professional."
            )
        )
    elif outcome == "available":
        call.set_task(
            "begin_intake",
            objective=(
                f"Complete a pre-visit intake call with {patient_name} ahead of their "
                f"appointment at Sunrise Family Practice on {appointment_date}. "
                "Collect their chief complaint, symptom duration, pain level, and current medications "
                "so the care team can prepare."
            ),
            checklist=[
                guava.Say(
                    f"Hello {patient_name}, this is Jamie calling from Sunrise Family Practice. "
                    f"I'm reaching out to collect a few details before your appointment on "
                    f"{appointment_date}. This should only take a couple of minutes and will "
                    "help your provider prepare for your visit."
                ),
                guava.Field(
                    key="chief_complaint",
                    field_type="text",
                    description=(
                        "Ask the patient what is the primary reason for their upcoming visit — "
                        "the main symptom or concern they want to discuss with their provider."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="symptom_duration",
                    field_type="text",
                    description=(
                        "Ask how long they have been experiencing the main symptom or concern. "
                        "For example: a few days, two weeks, several months."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="pain_scale",
                    field_type="multiple_choice",
                    description=(
                        "Ask the patient to rate their current discomfort or pain on a scale from "
                        "1 to 10, where 1 is very mild and 10 is the worst imaginable. "
                        "Group their answer into the closest bracket."
                    ),
                    choices=["1-3 mild", "4-6 moderate", "7-9 severe", "10 worst possible", "no pain"],
                    required=True,
                ),
                guava.Field(
                    key="current_medications",
                    field_type="text",
                    description=(
                        "Ask the patient to list any medications they are currently taking, "
                        "including prescription drugs, over-the-counter medications, vitamins, and supplements. "
                        "If they are not taking anything, capture 'none'."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="allergies",
                    field_type="text",
                    description=(
                        "Ask the patient if they have any known drug or food allergies. "
                        "If none, capture 'none'."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="additional_concerns",
                    field_type="text",
                    description=(
                        "Ask whether there is anything else the patient would like their provider "
                        "to know before the appointment. Skip if they have nothing to add."
                    ),
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("begin_intake")
def on_done(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")
    patient_id = call.get_variable("patient_id")
    appointment_date = call.get_variable("appointment_date")

    chief_complaint = call.get_field("chief_complaint")
    symptom_duration = call.get_field("symptom_duration")
    pain_scale = call.get_field("pain_scale")
    current_medications = call.get_field("current_medications")
    allergies = call.get_field("allergies")
    additional_concerns = call.get_field("additional_concerns")

    # Build a plain-text note to be stored as a DocumentReference.
    note_lines = [
        f"Pre-visit intake — Sunrise Family Practice",
        f"Patient: {patient_name}",
        f"Appointment: {appointment_date}",
        f"Collected: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        f"Chief complaint: {chief_complaint}",
        f"Symptom duration: {symptom_duration}",
        f"Pain/discomfort level: {pain_scale}",
        f"Current medications: {current_medications}",
        f"Known allergies: {allergies}",
    ]
    if additional_concerns:
        note_lines.append(f"Additional concerns: {additional_concerns}")
    note_text = "\n".join(note_lines)

    logging.info("Intake note assembled for patient %s:\n%s", patient_id, note_text)

    # Save the intake responses as a DocumentReference in Practice Fusion so the
    # care team can review them in the patient chart before the appointment.
    try:
        doc = create_document_reference(patient_id, note_text, appointment_date)
        doc_id = doc.get("id", "unknown")
        logging.info("DocumentReference created: %s", doc_id)
    except Exception as exc:
        logging.error(
            "Failed to create DocumentReference for patient %s: %s", patient_id, exc
        )

    call.hangup(
        final_instructions=(
            f"Thank {patient_name} for taking the time to complete the intake. "
            "Let them know their responses have been sent to their care team at Sunrise Family "
            f"Practice and will be reviewed before their appointment on {appointment_date}. "
            "Remind them to arrive about 10 minutes early. Wish them a great day."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound pre-visit intake call for Sunrise Family Practice via Practice Fusion FHIR R4."
    )
    parser.add_argument("phone", help="Patient phone number in E.164 format (e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Patient full name")
    parser.add_argument("--patient-id", required=True, help="Practice Fusion FHIR Patient resource ID")
    parser.add_argument(
        "--appointment-date",
        default="tomorrow",
        help="Appointment date string shown to the patient (e.g. 'Friday at 2:00 PM'). Default: 'tomorrow'.",
    )
    args = parser.parse_args()

    logging.info(
        "Initiating pre-visit intake call to %s (%s), patient ID %s, appointment %s",
        args.name,
        args.phone,
        args.patient_id,
        args.appointment_date,
    )

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "patient_name": args.name,
            "patient_id": args.patient_id,
            "appointment_date": args.appointment_date,
        },
    )

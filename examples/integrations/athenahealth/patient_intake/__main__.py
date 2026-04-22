import guava
import os
import logging
from guava import logging_utils
import argparse
import requests


PRACTICE_ID = os.environ["ATHENA_PRACTICE_ID"]
BASE_URL = f"https://api.platform.athenahealth.com/v1/{PRACTICE_ID}"


def get_access_token() -> str:
    resp = requests.post(
        "https://api.platform.athenahealth.com/oauth2/v1/token",
        data={"grant_type": "client_credentials"},
        auth=(os.environ["ATHENA_CLIENT_ID"], os.environ["ATHENA_CLIENT_SECRET"]),
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def get_patient_medications(patient_id: str, headers: dict) -> list:
    resp = requests.get(
        f"{BASE_URL}/patients/{patient_id}/medications",
        headers=headers,
        timeout=10,
    )
    if not resp.ok:
        return []
    return resp.json().get("medications", [])


def get_patient_allergies(patient_id: str, headers: dict) -> list:
    resp = requests.get(
        f"{BASE_URL}/patients/{patient_id}/allergies",
        headers=headers,
        timeout=10,
    )
    if not resp.ok:
        return []
    return resp.json().get("allergies", [])


def post_intake_document(patient_id: str, content: str, headers: dict) -> bool:
    """Posts a pre-visit intake summary as a document to the patient chart."""
    resp = requests.post(
        f"{BASE_URL}/patients/{patient_id}/documents",
        headers={**headers, "Content-Type": "application/x-www-form-urlencoded"},
        data={
            "documentsubclass": "LETTER",
            "internalnote": content,
            "status": "CLOSED",
        },
        timeout=10,
    )
    return resp.ok


agent = guava.Agent(
    name="Avery",
    organization="Maple Medical Group",
    purpose=(
        "to complete pre-visit intake for patients before their appointments"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(contact_full_name=call.get_variable("patient_name"))


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    if outcome == "unavailable":
        logging.info("Unable to reach %s for pre-visit intake.", call.get_variable("patient_name"))
        call.hangup(
            final_instructions=(
                f"Leave a brief voicemail for {call.get_variable('patient_name')} from Maple Medical Group. "
                "Let them know you're calling to complete a pre-visit intake before their "
                f"appointment on {call.get_variable('appointment_time')} and ask them to call back. "
                "Keep it friendly and concise."
            )
        )
    elif outcome == "available":
        patient_name = call.get_variable("patient_name")
        patient_id = call.get_variable("patient_id")
        appointment_time = call.get_variable("appointment_time")

        headers = {}
        existing_meds: list = []
        existing_allergies: list = []
        try:
            token = get_access_token()
            headers = {"Authorization": f"Bearer {token}"}
            existing_meds = get_patient_medications(patient_id, headers)
            existing_allergies = get_patient_allergies(patient_id, headers)
            logging.info(
                "Pre-call data loaded for patient %s: %d meds, %d allergies",
                patient_id, len(existing_meds), len(existing_allergies),
            )
        except Exception as e:
            logging.error("Failed to load patient pre-call data for %s: %s", patient_id, e)

        call.set_variable("headers", headers)

        med_names = [m.get("medicationname", "") for m in existing_meds if m.get("medicationname")]
        allergy_names = [a.get("allergenname", "") for a in existing_allergies if a.get("allergenname")]

        meds_context = (
            f"Medications on file: {', '.join(med_names)}. "
            "Confirm whether this list is still current and ask about any new medications."
            if med_names else
            "No medications on file. Ask what medications they are currently taking."
        )
        allergies_context = (
            f"Allergies on file: {', '.join(allergy_names)}. "
            "Confirm accuracy and ask about any new allergies."
            if allergy_names else
            "No allergies on file. Ask if they have any known drug or environmental allergies."
        )

        call.set_task(
            "save_intake",
            objective=(
                f"Complete pre-visit intake for {patient_name} ahead of their appointment "
                f"on {appointment_time}. Collect their chief complaint, confirm current "
                "medications and allergies, and note any changes since their last visit."
            ),
            checklist=[
                guava.Say(
                    f"Hi {patient_name}, this is Avery calling from Maple Medical Group. "
                    f"I'm calling to complete a quick pre-visit intake ahead of your appointment "
                    f"on {appointment_time}. It should only take a few minutes."
                ),
                guava.Field(
                    key="chief_complaint",
                    field_type="text",
                    description=(
                        "Ask what the main reason is for their upcoming visit. "
                        "What symptoms or concerns are they coming in for?"
                    ),
                    required=True,
                ),
                guava.Field(
                    key="medications_confirmed",
                    field_type="text",
                    description=meds_context,
                    required=True,
                ),
                guava.Field(
                    key="allergies_confirmed",
                    field_type="text",
                    description=allergies_context,
                    required=True,
                ),
                guava.Field(
                    key="recent_changes",
                    field_type="text",
                    description=(
                        "Ask if there have been any significant health changes since their last visit — "
                        "new diagnoses, hospitalizations, or changes in symptoms."
                    ),
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("save_intake")
def on_done(call: guava.Call) -> None:
    complaint = call.get_field("chief_complaint") or ""
    meds = call.get_field("medications_confirmed") or ""
    allergies = call.get_field("allergies_confirmed") or ""
    changes = call.get_field("recent_changes") or "None reported"
    patient_name = call.get_variable("patient_name")
    patient_id = call.get_variable("patient_id")
    appointment_time = call.get_variable("appointment_time")
    headers = call.get_variable("headers") or {}

    summary = (
        f"Pre-visit intake — {appointment_time}\n"
        f"Chief complaint: {complaint}\n"
        f"Medications: {meds}\n"
        f"Allergies: {allergies}\n"
        f"Recent changes: {changes}"
    )
    logging.info("Intake summary for patient %s:\n%s", patient_id, summary)

    try:
        posted = post_intake_document(patient_id, summary, headers)
        logging.info("Intake document posted to chart: %s", posted)
    except Exception as e:
        logging.error("Failed to post intake document for patient %s: %s", patient_id, e)

    call.hangup(
        final_instructions=(
            f"Thank {patient_name} for completing the intake. "
            "Let them know the care team will review this before their visit. "
            "Remind them to arrive 10–15 minutes early and bring their insurance card. "
            "Wish them a great day."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound pre-visit patient intake via Athenahealth."
    )
    parser.add_argument("phone", help="Patient phone number (E.164, e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Patient's full name")
    parser.add_argument("--patient-id", required=True, help="Athenahealth patient ID")
    parser.add_argument("--appointment", required=True, help="Appointment date/time (display string)")
    args = parser.parse_args()

    logging.info(
        "Starting pre-visit intake call to %s (%s), appointment: %s",
        args.name, args.phone, args.appointment,
    )

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "patient_name": args.name,
            "patient_id": args.patient_id,
            "appointment_time": args.appointment,
        },
    )

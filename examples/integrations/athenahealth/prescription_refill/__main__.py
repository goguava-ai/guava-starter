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


def request_refill(patient_id: str, medication: str, pharmacy: str, headers: dict) -> bool:
    """Creates a medication refill request in the patient chart."""
    resp = requests.post(
        f"{BASE_URL}/patients/{patient_id}/medications",
        headers={**headers, "Content-Type": "application/x-www-form-urlencoded"},
        data={
            "medicationname": medication,
            "refillrequestreason": f"Patient requested refill via phone. Preferred pharmacy: {pharmacy}",
            "issafetorenew": "true",
        },
        timeout=10,
    )
    return resp.ok


agent = guava.Agent(
    name="Avery",
    organization="Maple Medical Group",
    purpose=(
        "to help patients request prescription refills quickly and route them to the care team"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(contact_full_name=call.get_variable("patient_name"))


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    if outcome == "unavailable":
        logging.info("Unable to reach %s for prescription refill.", call.get_variable("patient_name"))
        call.hangup(
            final_instructions=(
                f"Leave a brief voicemail for {call.get_variable('patient_name')} from Maple Medical Group. "
                f"Let them know you're calling regarding a refill for {call.get_variable('medication')} "
                "and ask them to call back to confirm their pharmacy preference. "
                "Keep it concise."
            )
        )
    elif outcome == "available":
        patient_name = call.get_variable("patient_name")
        patient_id = call.get_variable("patient_id")
        medication = call.get_variable("medication")

        headers = {}
        try:
            token = get_access_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/x-www-form-urlencoded",
            }
        except Exception as e:
            logging.error("Failed to get Athenahealth token: %s", e)

        call.data = {"headers": headers}

        call.set_task(
            "submit_refill",
            objective=(
                f"Call {patient_name} about a refill for {medication}. Confirm they still need "
                "the refill, check for any new symptoms or concerns, and collect their preferred pharmacy."
            ),
            checklist=[
                guava.Say(
                    f"Hi {patient_name}, this is Avery calling from Maple Medical Group "
                    f"regarding a refill request for {medication}."
                ),
                guava.Field(
                    key="still_needs_refill",
                    field_type="multiple_choice",
                    description="Confirm the patient still needs the refill.",
                    choices=["yes", "no"],
                    required=True,
                ),
                guava.Field(
                    key="new_symptoms",
                    field_type="multiple_choice",
                    description=(
                        "Ask if they've experienced any new or worsening symptoms since "
                        "they last took this medication."
                    ),
                    choices=["yes", "no"],
                    required=True,
                ),
                guava.Field(
                    key="symptom_details",
                    field_type="text",
                    description=(
                        "If they said yes to new symptoms, ask them to briefly describe what they've noticed. "
                        "Skip this if they said no."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="pharmacy",
                    field_type="text",
                    description=(
                        "Ask which pharmacy they'd like the prescription sent to. "
                        "Capture name and location (e.g., 'CVS on Main Street')."
                    ),
                    required=True,
                ),
            ],
        )


@agent.on_task_complete("submit_refill")
def on_done(call: guava.Call) -> None:
    still_needs = call.get_field("still_needs_refill") or ""
    pharmacy = call.get_field("pharmacy") or "patient's preferred pharmacy"
    symptoms = call.get_field("symptom_details") or ""
    patient_name = call.get_variable("patient_name")
    patient_id = call.get_variable("patient_id")
    medication = call.get_variable("medication")
    headers = call.data.get("headers", {}) if call.data else {}

    if "no" in still_needs:
        logging.info("Patient %s no longer needs refill for %s.", patient_id, medication)
        call.hangup(
            final_instructions=(
                f"Acknowledge that {patient_name} no longer needs the refill. "
                "Let them know no action will be taken and that they can call back anytime. "
                "Wish them a great day."
            )
        )
        return

    logging.info(
        "Submitting refill for patient %s: %s → %s",
        patient_id, medication, pharmacy,
    )

    success = False
    try:
        success = request_refill(patient_id, medication, pharmacy, headers)
        logging.info("Refill request submitted: %s", success)
    except Exception as e:
        logging.error("Failed to submit refill for patient %s: %s", patient_id, e)

    symptom_note = (
        f" Note: patient reported new symptoms — '{symptoms}'. The care team should review before approving."
        if symptoms else ""
    )

    if success:
        call.hangup(
            final_instructions=(
                f"Let {patient_name} know their refill request for {medication} "
                f"has been submitted to the care team and will be sent to {pharmacy}. "
                f"Let them know to expect it within 1–2 business days.{symptom_note} "
                "Thank them for calling and wish them a great day."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Apologize to {patient_name} — let them know there was an issue submitting "
                "the refill request and that a team member will follow up by end of day. "
                "Thank them for their patience."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound prescription refill confirmation via Athenahealth."
    )
    parser.add_argument("phone", help="Patient phone number (E.164, e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Patient's full name")
    parser.add_argument("--patient-id", required=True, help="Athenahealth patient ID")
    parser.add_argument("--medication", required=True, help="Medication name and dosage (e.g. 'Lisinopril 10mg')")
    args = parser.parse_args()

    logging.info(
        "Initiating prescription refill call to %s (%s) for %s",
        args.name, args.phone, args.medication,
    )

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "patient_name": args.name,
            "patient_id": args.patient_id,
            "medication": args.medication,
        },
    )

import guava
import os
import logging
from guava import logging_utils
import argparse
import requests



def get_access_token() -> str:
    resp = requests.post(
        os.environ["ECW_TOKEN_URL"],
        data={"grant_type": "client_credentials", "scope": "system/*.read system/*.write"},
        auth=(os.environ["ECW_CLIENT_ID"], os.environ["ECW_CLIENT_SECRET"]),
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def post_medication_request(patient_id: str, medication: str, pharmacy: str, headers: dict) -> bool:
    base_url = os.environ["ECW_BASE_URL"]
    payload = {
        "resourceType": "MedicationRequest",
        "status": "active",
        "intent": "order",
        "medicationCodeableConcept": {"text": medication},
        "subject": {"reference": f"Patient/{patient_id}"},
        "reasonCode": [{"text": "Patient-requested refill via phone"}],
        "note": [{"text": f"Preferred pharmacy: {pharmacy}"}],
    }
    resp = requests.post(f"{base_url}/MedicationRequest", headers=headers, json=payload, timeout=10)
    return resp.ok


agent = guava.Agent(
    name="Sam",
    organization="Sunrise Family Practice",
    purpose="to process prescription refill requests for patients",
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")
    headers = {}
    try:
        token = get_access_token()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    except Exception as e:
        logging.error("Token error: %s", e)
    call.set_variable("headers", headers)

    call.reach_person(contact_full_name=patient_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    patient_name = call.get_variable("patient_name")
    medication = call.get_variable("medication")
    if outcome == "unavailable":
        call.hangup(
            final_instructions=(
                f"Leave a voicemail for {patient_name} from Sunrise Family Practice "
                f"about their {medication} refill. Ask them to call back to confirm their pharmacy. "
                "Keep it brief."
            )
        )
    elif outcome == "available":
        call.set_task(
            "prescription_refill",
            objective=(
                f"Call {patient_name} regarding a refill request for {medication}. "
                "Confirm they still need it, check for new symptoms, and collect their pharmacy."
            ),
            checklist=[
                guava.Say(
                    f"Hi {patient_name}, this is Sam calling from Sunrise Family Practice "
                    f"about a prescription refill for {medication}."
                ),
                guava.Field(
                    key="still_needs_refill",
                    field_type="multiple_choice",
                    description="Confirm the patient still needs this refill.",
                    choices=["yes", "no"],
                    required=True,
                ),
                guava.Field(
                    key="new_symptoms",
                    field_type="multiple_choice",
                    description="Ask if they've experienced any new or worsening symptoms on this medication.",
                    choices=["yes", "no"],
                    required=True,
                ),
                guava.Field(
                    key="symptom_details",
                    field_type="text",
                    description="If yes to new symptoms, ask them to describe briefly. Skip if no.",
                    required=False,
                ),
                guava.Field(
                    key="pharmacy",
                    field_type="text",
                    description="Ask which pharmacy they'd like it sent to (name and location).",
                    required=True,
                ),
            ],
        )


@agent.on_task_complete("prescription_refill")
def on_done(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")
    patient_id = call.get_variable("patient_id")
    medication = call.get_variable("medication")
    still_needs = call.get_field("still_needs_refill") or ""
    pharmacy = call.get_field("pharmacy") or "preferred pharmacy"
    symptoms = call.get_field("symptom_details") or ""

    if "no" in still_needs:
        logging.info("Patient %s no longer needs refill.", patient_id)
        call.hangup(
            final_instructions=(
                f"Acknowledge that {patient_name} no longer needs the refill. "
                "Thank them for letting us know and wish them a great day."
            )
        )
        return

    success = False
    try:
        success = post_medication_request(patient_id, medication, pharmacy, call.get_variable("headers"))
        logging.info("MedicationRequest posted: %s", success)
    except Exception as e:
        logging.error("Failed to post MedicationRequest: %s", e)

    symptom_note = (
        f" Note: patient reported new symptoms — '{symptoms}'. Care team should review before approving."
        if symptoms else ""
    )

    if success:
        call.hangup(
            final_instructions=(
                f"Let {patient_name} know their refill request for {medication} "
                f"has been submitted to the care team and will be sent to {pharmacy}. "
                f"Expect it within 1–2 business days.{symptom_note} "
                "Thank them and wish them a great day."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Apologize to {patient_name} — the refill request couldn't be submitted. "
                "Let them know a team member will follow up shortly. Thank them for their patience."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(description="Outbound prescription refill via eClinicalWorks FHIR.")
    parser.add_argument("phone", help="Patient phone number (E.164)")
    parser.add_argument("--name", required=True)
    parser.add_argument("--patient-id", required=True)
    parser.add_argument("--medication", required=True)
    args = parser.parse_args()

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "patient_name": args.name,
            "patient_id": args.patient_id,
            "medication": args.medication,
        },
    )

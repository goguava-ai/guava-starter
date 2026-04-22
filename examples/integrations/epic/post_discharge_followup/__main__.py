import guava
import os
import logging
from guava import logging_utils
import json
import requests
import argparse
from datetime import datetime, timezone


agent = guava.Agent(
    name="Sam",
    organization="Cedar Health",
    purpose=(
        "to follow up with recently discharged patients, check on their recovery, "
        "assess pain levels, and confirm medication adherence on behalf of Cedar Health"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")
    call.reach_person(contact_full_name=patient_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    patient_name = call.get_variable("patient_name")
    if outcome == "unavailable":
        call.hangup(
            final_instructions=(
                "We were unable to reach the patient. Leave a caring voicemail on behalf of "
                "Cedar Health letting them know we called to check on their recovery and asking "
                "them to call us back at their earliest convenience."
            )
        )
    elif outcome == "available":
        call.set_task(
            "post_discharge_followup",
            objective=(
                f"Conduct a post-discharge follow-up with {patient_name} from Cedar Health. "
                "Assess recovery status, pain level, and medication adherence. Identify any "
                "concerning symptoms that require clinical attention."
            ),
            checklist=[
                guava.Say(
                    f"Hello {patient_name}, this is Sam calling from Cedar Health. "
                    "We're checking in to see how you're doing since your recent discharge "
                    "and to make sure your recovery is going well."
                ),
                guava.Field(
                    key="recovery_status",
                    description=(
                        "Ask the patient how their overall recovery is going since discharge. "
                        "Capture a brief summary in their own words."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="pain_level",
                    description=(
                        "Ask the patient to rate their current pain level on a scale from 0 to 10, "
                        "where 0 is no pain and 10 is the worst pain imaginable."
                    ),
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="medication_adherence",
                    description=(
                        "Ask whether the patient has been taking all discharge medications exactly "
                        "as prescribed. Capture their response (e.g., 'yes', 'no', 'missed a few doses')."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="concerning_symptoms",
                    description=(
                        "Ask if the patient has experienced any concerning symptoms since discharge, "
                        "such as fever, unusual swelling, shortness of breath, or wound changes. "
                        "Capture any symptoms they describe. Skip if they have none."
                    ),
                    field_type="text",
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("post_discharge_followup")
def on_done(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")
    patient_id = call.get_variable("patient_id")
    recovery_status = call.get_field("recovery_status")
    pain_level = call.get_field("pain_level")
    medication_adherence = call.get_field("medication_adherence")
    concerning_symptoms = call.get_field("concerning_symptoms")

    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": "Sam",
        "organization": "Cedar Health",
        "use_case": "post_discharge_followup",
        "patient_name": patient_name,
        "patient_id": patient_id,
        "fields": {
            "recovery_status": recovery_status,
            "pain_level": pain_level,
            "medication_adherence": medication_adherence,
            "concerning_symptoms": concerning_symptoms,
        },
    }
    print(json.dumps(results, indent=2))
    logging.info("Post-discharge follow-up results saved locally.")

    # Post-call: write a single Observation to Epic summarizing the follow-up.
    # Category "survey" + LOINC 72166-2 flags this as a post-discharge check-in
    # so the care team can easily filter for it in the patient's timeline.
    try:
        base_url = os.environ["EPIC_BASE_URL"]
        access_token = os.environ["EPIC_ACCESS_TOKEN"]
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        obs_payload = {
            "resourceType": "Observation",
            "status": "final",
            "category": [
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                            "code": "survey",
                            "display": "Survey",
                        }
                    ]
                }
            ],
            "code": {
                "coding": [{"system": "http://loinc.org", "code": "72166-2", "display": "Post-discharge follow-up"}]
            },
            "subject": {"reference": f"Patient/{patient_id}"},
            "effectiveDateTime": datetime.now(timezone.utc).isoformat(),
            "valueString": (
                f"Recovery: {recovery_status}. "
                f"Pain: {pain_level}/10. "
                f"Meds as prescribed: {medication_adherence}. "
                f"Concerning symptoms: {concerning_symptoms or 'None reported'}."
            ),
        }

        resp = requests.post(
            f"{base_url}/Observation",
            headers=headers,
            json=obs_payload,
            timeout=10,
        )
        resp.raise_for_status()
        obs_id = resp.json().get("id", "")
        logging.info("Epic Observation created: %s", obs_id)
    except Exception as e:
        logging.error("Failed to create Epic Observation: %s", e)

    # Risk-stratify the close: escalate if pain is high or symptoms were reported.
    high_pain = isinstance(pain_level, int) and pain_level >= 7
    has_symptoms = concerning_symptoms and str(concerning_symptoms).strip()

    if high_pain or has_symptoms:
        call.hangup(
            final_instructions=(
                "Express genuine concern for the patient's wellbeing. Let them know their "
                "responses will be flagged for urgent clinical review and a care team member "
                "will reach out shortly. Advise them to call 911 or go to the nearest emergency "
                "room if their condition worsens. Thank them and wish them a speedy recovery."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                "Thank the patient for their time. Let them know their responses have been "
                "recorded and the care team at Cedar Health will review them. Remind them "
                "they can call the clinic any time with questions. Wish them a smooth recovery."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound post-discharge follow-up call for Cedar Health via Epic FHIR."
    )
    parser.add_argument("phone", help="Patient phone number to call (E.164 format, e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Full name of the patient")
    parser.add_argument("--patient-id", required=True, help="Epic Patient FHIR resource ID")
    args = parser.parse_args()

    logging.info(
        "Initiating post-discharge follow-up call to %s (%s), patient ID: %s",
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
        },
    )

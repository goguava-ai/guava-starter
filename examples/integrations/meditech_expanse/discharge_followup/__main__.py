import guava
import os
import logging
from guava import logging_utils
import argparse
import requests
from datetime import datetime, timezone


FHIR_BASE_URL = os.environ["MEDITECH_FHIR_BASE_URL"]


def get_headers() -> dict:
    return {
        "Authorization": f"Bearer {os.environ['MEDITECH_ACCESS_TOKEN']}",
        "Content-Type": "application/json",
        "Accept": "application/fhir+json",
    }


agent = guava.Agent(
    name="Riley",
    organization="St. Raphael Medical Center",
    purpose=(
        "to check in with recently discharged patients and ensure they are "
        "recovering well after leaving St. Raphael Medical Center"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")
    call.reach_person(contact_full_name=patient_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    patient_name = call.get_variable("patient_name")
    patient_id = call.get_variable("patient_id")
    discharge_date = call.get_variable("discharge_date")

    if outcome == "unavailable":
        call.hangup(
            final_instructions=(
                f"Leave a brief, caring voicemail for {patient_name} on behalf of "
                "St. Raphael Medical Center. Let them know we called to check on their "
                f"recovery following their discharge on {discharge_date}. "
                "Ask them to call us back at their earliest convenience. "
                "Keep the message under 30 seconds."
            )
        )
    elif outcome == "available":
        # Fetch the most recent finished Encounter so we can personalize the greeting
        # with the patient's discharge reason and link Observations back to the encounter.
        encounter_id = None
        encounter_summary = "your recent hospital stay"
        try:
            enc_resp = requests.get(
                f"{FHIR_BASE_URL}/Encounter",
                headers=get_headers(),
                params={
                    "patient": f"Patient/{patient_id}",
                    "status": "finished",
                    "_sort": "-date",
                    "_count": "1",
                },
                timeout=10,
            )
            enc_resp.raise_for_status()
            entries = enc_resp.json().get("entry", [])
            if entries:
                enc = entries[0]["resource"]
                encounter_id = enc.get("id")
                reason_list = enc.get("reasonCode", [])
                reason_text = reason_list[0].get("text") if reason_list else None
                encounter_summary = reason_text or "your recent hospital stay"
                logging.info(
                    "Fetched encounter %s for patient %s: %s",
                    encounter_id,
                    patient_id,
                    encounter_summary,
                )
            else:
                logging.warning(
                    "No finished encounters found for patient %s.", patient_id
                )
        except Exception as e:
            logging.error("Failed to fetch Meditech Encounter: %s", e)

        call.encounter_id = encounter_id
        call.encounter_summary = encounter_summary

        call.set_task(
            "collect_wellness_info",
            objective=(
                f"Conduct a post-discharge wellness check with {patient_name}, discharged "
                f"from St. Raphael Medical Center on {discharge_date}. Collect their pain "
                "level, medication adherence, and any concerning symptoms. Escalate immediately "
                "if they report alarming symptoms."
            ),
            checklist=[
                guava.Say(
                    f"Hi {patient_name}, this is Riley calling from "
                    f"St. Raphael Medical Center. We are following up on your discharge on "
                    f"{discharge_date} related to {encounter_summary}. "
                    "We want to make sure you are recovering well. Do you have a few minutes?"
                ),
                guava.Field(
                    key="pain_level",
                    description=(
                        "Ask the patient to rate their current pain level on a scale from "
                        "0 to 10, where 0 is no pain and 10 is the worst pain imaginable. "
                        "Capture the numeric value as a string (e.g. '3')."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="medication_adherence",
                    description=(
                        "Ask whether the patient has been taking all of their prescribed "
                        "discharge medications as directed. Options are: yes — taking all as "
                        "directed, no — stopped taking one or more, or not yet — have not "
                        "picked them up."
                    ),
                    field_type="multiple_choice",
                    choices=[
                        "yes, taking as directed",
                        "no, stopped one or more",
                        "not yet picked up",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="concerning_symptoms",
                    description=(
                        "Ask whether the patient has experienced any concerning symptoms since "
                        "coming home, such as fever, severe pain, shortness of breath, chest pain, "
                        "unusual swelling, wound changes, confusion, or fainting. "
                        "Capture 'yes' or 'no'."
                    ),
                    field_type="multiple_choice",
                    choices=["yes", "no"],
                    required=True,
                ),
                guava.Field(
                    key="symptom_description",
                    description=(
                        "If the patient said yes to concerning symptoms, ask them to briefly "
                        "describe what they are experiencing. If they said no, capture 'none'."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="followup_scheduled",
                    description=(
                        "Ask whether the patient already has a follow-up appointment scheduled "
                        "with their doctor or specialist. Options are: yes, no, or need help scheduling."
                    ),
                    field_type="multiple_choice",
                    choices=["yes", "no", "need help scheduling"],
                    required=True,
                ),
            ],
        )


@agent.on_task_complete("collect_wellness_info")
def process_and_close(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")
    patient_id = call.get_variable("patient_id")
    pain_level = call.get_field("pain_level")
    medication_adherence = call.get_field("medication_adherence")
    concerning_symptoms = call.get_field("concerning_symptoms")
    symptom_description = call.get_field("symptom_description")
    followup_scheduled = call.get_field("followup_scheduled")
    encounter_id = call.encounter_id

    has_concerning_symptoms = (
        concerning_symptoms and concerning_symptoms.strip().lower() == "yes"
    )

    try:
        pain_score = int(pain_level.strip())
    except (ValueError, AttributeError):
        pain_score = 0

    escalate = has_concerning_symptoms or pain_score >= 7

    # Post the wellness check results as a FHIR Observation bundle to Meditech Expanse.
    # Each data point becomes an individual Observation so the care team can query
    # specific values (e.g., pain score) directly from the clinical timeline.
    _post_observation_bundle(
        patient_id=patient_id,
        encounter_id=encounter_id,
        pain_level=pain_level,
        pain_score=pain_score,
        medication_adherence=medication_adherence,
        concerning_symptoms=concerning_symptoms,
        symptom_description=symptom_description,
        followup_scheduled=followup_scheduled,
        escalate=escalate,
    )

    if escalate:
        _escalate_to_care_team(patient_id, pain_score, symptom_description)
        call.hangup(
            final_instructions=(
                f"Express genuine concern for {patient_name}'s wellbeing. "
                "Let them know their symptoms sound serious and need prompt attention. "
                "Strongly advise them to call 911 immediately if they feel their condition "
                "is life-threatening, or to go to the nearest emergency room. "
                "Let them know their care team at St. Raphael Medical Center has been "
                "alerted and someone will follow up with them very shortly. "
                "Stay calm and reassuring."
            )
        )
        return

    closing_notes: list[str] = []

    if medication_adherence and medication_adherence.strip().lower() in (
        "no, stopped one or more",
        "not yet picked up",
    ):
        closing_notes.append(
            "Gently remind them that taking discharge medications as prescribed is a "
            "critical part of their recovery. Let them know our pharmacy team is available "
            "to help if they have any barriers to filling or taking their prescriptions."
        )

    if followup_scheduled and followup_scheduled.strip().lower() == "need help scheduling":
        closing_notes.append(
            "Offer to transfer them to our scheduling line, or let them know they can "
            "call St. Raphael Medical Center at any time to set up their follow-up visit."
        )
    elif followup_scheduled and followup_scheduled.strip().lower() == "no":
        closing_notes.append(
            "Encourage them to schedule a follow-up with their primary care provider "
            "or specialist soon to support their continued recovery."
        )

    extra = " ".join(closing_notes)

    call.hangup(
        final_instructions=(
            f"Thank {patient_name} warmly for taking the time to speak with us today. "
            f"{extra} "
            "Let them know their responses have been recorded and shared with their care team "
            "at St. Raphael Medical Center. Remind them they can call us any time with "
            "questions or concerns. Wish them a smooth and speedy recovery."
        ).strip()
    )


def _post_observation_bundle(
    patient_id: str,
    encounter_id: str | None,
    pain_level: str,
    pain_score: int,
    medication_adherence: str,
    concerning_symptoms: str,
    symptom_description: str,
    followup_scheduled: str,
    escalate: bool,
):
    """POST a FHIR transaction Bundle of Observations capturing all wellness check data points."""
    now = datetime.now(timezone.utc).isoformat()
    subject_ref = {"reference": f"Patient/{patient_id}"}
    encounter_ref = (
        {"reference": f"Encounter/{encounter_id}"} if encounter_id else None
    )

    def make_obs(loinc_code: str, display: str, value_str: str) -> dict:
        obs: dict = {
            "resourceType": "Observation",
            "status": "final",
            "category": [
                {
                    "coding": [
                        {
                            "system": (
                                "http://terminology.hl7.org/CodeSystem/observation-category"
                            ),
                            "code": "survey",
                            "display": "Survey",
                        }
                    ]
                }
            ],
            "code": {
                "coding": [
                    {
                        "system": "http://loinc.org",
                        "code": loinc_code,
                        "display": display,
                    }
                ],
                "text": display,
            },
            "subject": subject_ref,
            "effectiveDateTime": now,
            "valueString": value_str,
        }
        if encounter_ref:
            obs["encounter"] = encounter_ref
        return obs

    # LOINC 72514-3: Pain severity verbal numeric rating [Score]
    pain_obs = make_obs("72514-3", "Pain severity verbal numeric rating", pain_level)
    try:
        pain_obs["valueQuantity"] = {
            "value": pain_score,
            "system": "http://unitsofmeasure.org",
            "code": "{score}",
        }
        del pain_obs["valueString"]
    except Exception:
        pass

    bundle = {
        "resourceType": "Bundle",
        "type": "transaction",
        "entry": [
            {
                "resource": pain_obs,
                "request": {"method": "POST", "url": "Observation"},
            },
            {
                "resource": make_obs(
                    "418633004",
                    "Medication adherence",
                    medication_adherence,
                ),
                "request": {"method": "POST", "url": "Observation"},
            },
            {
                "resource": make_obs(
                    "75325-1",
                    "Post-discharge symptom report",
                    f"Concerning symptoms: {concerning_symptoms}. "
                    f"Description: {symptom_description}.",
                ),
                "request": {"method": "POST", "url": "Observation"},
            },
            {
                "resource": make_obs(
                    "72166-2",
                    "Post-discharge follow-up summary",
                    f"Follow-up scheduled: {followup_scheduled}. "
                    f"Escalated: {'yes' if escalate else 'no'}.",
                ),
                "request": {"method": "POST", "url": "Observation"},
            },
        ],
    }

    try:
        resp = requests.post(
            FHIR_BASE_URL,
            headers=get_headers(),
            json=bundle,
            timeout=15,
        )
        resp.raise_for_status()
        logging.info(
            "Posted discharge follow-up Observation bundle for patient %s.",
            patient_id,
        )
    except Exception as e:
        logging.error(
            "Failed to post Observation bundle for patient %s: %s",
            patient_id,
            e,
        )


def _escalate_to_care_team(patient_id: str, pain_score: int, symptom_description: str):
    """Create a FHIR Flag resource in Meditech to alert the care team."""
    flag_payload = {
        "resourceType": "Flag",
        "status": "active",
        "category": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/flag-category",
                        "code": "clinical",
                        "display": "Clinical",
                    }
                ]
            }
        ],
        "code": {
            "coding": [
                {
                    "system": "http://snomed.info/sct",
                    "code": "394848005",
                    "display": "Clinical concern",
                }
            ],
            "text": (
                f"Post-discharge follow-up escalation — pain score: {pain_score}/10, "
                f"symptoms: {symptom_description}. Immediate clinical review required."
            ),
        },
        "subject": {"reference": f"Patient/{patient_id}"},
        "period": {"start": datetime.now(timezone.utc).isoformat()},
        "author": {"display": "Guava Voice Agent — Riley"},
    }
    try:
        resp = requests.post(
            f"{FHIR_BASE_URL}/Flag",
            headers=get_headers(),
            json=flag_payload,
            timeout=10,
        )
        resp.raise_for_status()
        logging.warning(
            "ESCALATION: Created care team Flag for patient %s (pain=%d, symptoms=%s).",
            patient_id,
            pain_score,
            symptom_description,
        )
    except Exception as e:
        logging.error(
            "Failed to create escalation Flag for patient %s: %s",
            patient_id,
            e,
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description=(
            "Outbound post-discharge wellness follow-up for St. Raphael Medical Center "
            "via Meditech Expanse FHIR."
        )
    )
    parser.add_argument(
        "phone",
        help="Patient phone number to call (E.164 format, e.g. +15551234567)",
    )
    parser.add_argument("--name", required=True, help="Full name of the patient")
    parser.add_argument(
        "--patient-id",
        required=True,
        help="Meditech Expanse Patient FHIR resource ID",
    )
    parser.add_argument(
        "--discharge-date",
        required=True,
        help="Discharge date shown to the patient (e.g. 2026-03-28)",
    )
    args = parser.parse_args()

    logging.info(
        "Initiating discharge follow-up call to %s (%s), patient ID: %s, discharge: %s",
        args.name,
        args.phone,
        args.patient_id,
        args.discharge_date,
    )

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "patient_name": args.name,
            "patient_id": args.patient_id,
            "discharge_date": args.discharge_date,
        },
    )

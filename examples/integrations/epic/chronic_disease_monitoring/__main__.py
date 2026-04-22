import guava
import os
import logging
from guava import logging_utils
import json
import requests
import argparse
from datetime import datetime, timezone


agent = guava.Agent(
    name="Jamie",
    organization="Cedar Health",
    purpose=(
        "to collect remote health monitoring data from patients managing chronic conditions "
        "and post their readings to Epic on behalf of Cedar Health"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")
    patient_id = call.get_variable("patient_id")

    has_hypertension = False
    has_diabetes = False
    has_weight_management = False

    # Pre-call: fetch the patient's active conditions from Epic to determine which
    # vitals are relevant. A diabetic patient shouldn't be asked about blood pressure
    # unless they also have hypertension. If the fetch fails, all vitals are collected
    # as a safe default rather than skipping any potentially important readings.
    try:
        base_url = os.environ["EPIC_BASE_URL"]
        access_token = os.environ["EPIC_ACCESS_TOKEN"]
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        resp = requests.get(
            f"{base_url}/Condition",
            headers=headers,
            params={"patient": patient_id, "clinical-status": "active"},
            timeout=10,
        )
        resp.raise_for_status()
        for entry in resp.json().get("entry", []):
            resource = entry.get("resource", {})
            codings = resource.get("code", {}).get("coding", [])
            combined = " ".join(
                c.get("display", "") + " " + c.get("code", "")
                for c in codings
            ).lower() + " " + resource.get("code", {}).get("text", "").lower()

            if any(k in combined for k in ("hypertension", "blood pressure", "cardiovascular", "heart failure", "coronary")):
                has_hypertension = True
            if any(k in combined for k in ("diabetes", "diabetic", "glucose", "hyperglycemia", "a1c")):
                has_diabetes = True
            if any(k in combined for k in ("obesity", "overweight", "weight management", "bmi", "morbid obesity")):
                has_weight_management = True

        logging.info(
            "Active conditions for patient %s — hypertension: %s, diabetes: %s, weight management: %s",
            patient_id,
            has_hypertension,
            has_diabetes,
            has_weight_management,
        )
    except Exception as e:
        logging.error("Failed to fetch Epic Conditions: %s", e)
        # Default to collecting all vitals if the fetch fails
        has_hypertension = True
        has_diabetes = True
        has_weight_management = True

    call.has_hypertension = has_hypertension
    call.has_diabetes = has_diabetes
    call.has_weight_management = has_weight_management

    call.reach_person(contact_full_name=patient_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    patient_name = call.get_variable("patient_name")
    if outcome == "unavailable":
        call.hangup(
            final_instructions=(
                f"We were unable to reach {patient_name}. Leave a brief voicemail on behalf of "
                "Cedar Health asking them to call back to complete their routine health check-in "
                "or to log their readings in the patient portal."
            )
        )
    elif outcome == "available":
        # Build the checklist at runtime based on the condition flags set in on_call_start.
        # If no recognized conditions were found (e.g. Epic had no matching codes), collect
        # all vitals as a safe default rather than presenting an empty checklist.
        collect_all = not any([call.has_hypertension, call.has_diabetes, call.has_weight_management])

        vitals_being_collected = []
        if call.has_hypertension or collect_all:
            vitals_being_collected.append("blood pressure")
        if call.has_diabetes or collect_all:
            vitals_being_collected.append("blood glucose")
        if call.has_weight_management or collect_all:
            vitals_being_collected.append("weight")

        checklist = [
            guava.Say(
                f"Hi {patient_name}, this is Jamie calling from Cedar Health. "
                "I'm calling for your routine health check-in to collect today's readings. "
                "This will just take a couple of minutes."
            ),
        ]

        if call.has_hypertension or collect_all:
            checklist.append(
                guava.Field(
                    key="blood_pressure_systolic",
                    description=(
                        "Ask the patient for their systolic blood pressure reading (the top number) "
                        "from their home blood pressure cuff taken today. If they have not taken it, "
                        "capture 'not measured'."
                    ),
                    field_type="text",
                    required=True,
                )
            )
            checklist.append(
                guava.Field(
                    key="blood_pressure_diastolic",
                    description=(
                        "Ask the patient for their diastolic blood pressure reading (the bottom number) "
                        "from the same measurement. Skip if they said not measured."
                    ),
                    field_type="text",
                    required=False,
                )
            )

        if call.has_diabetes or collect_all:
            checklist.append(
                guava.Field(
                    key="blood_glucose",
                    description=(
                        "Ask for their blood glucose level in mg/dL from today's reading. "
                        "If they did not measure it today, capture 'not measured'."
                    ),
                    field_type="text",
                    required=True,
                )
            )

        if call.has_weight_management or collect_all:
            checklist.append(
                guava.Field(
                    key="weight",
                    description=(
                        "Ask for their current weight in pounds from today's measurement. "
                        "If they did not weigh themselves today, capture 'not measured'."
                    ),
                    field_type="text",
                    required=True,
                )
            )

        checklist.append(
            guava.Field(
                key="symptoms",
                description=(
                    "Ask if the patient has experienced any symptoms today such as shortness of breath, "
                    "dizziness, chest pain, swelling, or unusual fatigue. Capture what they describe. "
                    "If none, capture 'none'."
                ),
                field_type="text",
                required=True,
            )
        )
        checklist.append(
            guava.Field(
                key="medication_adherence",
                description=(
                    "Ask whether the patient took all of their medications as prescribed today. "
                    "Capture 'yes', 'no', or 'missed a dose' with details if provided."
                ),
                field_type="text",
                required=True,
            )
        )

        call.set_task(
            "chronic_disease_monitoring",
            objective=(
                f"Collect today's health readings from {patient_name} based on their active "
                f"conditions: {', '.join(vitals_being_collected) if vitals_being_collected else 'all vitals'}. "
                "Also record any symptoms and medication adherence."
            ),
            checklist=checklist,
        )


@agent.on_task_complete("chronic_disease_monitoring")
def on_done(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")
    patient_id = call.get_variable("patient_id")
    bp_systolic = call.get_field("blood_pressure_systolic")
    bp_diastolic = call.get_field("blood_pressure_diastolic")
    glucose = call.get_field("blood_glucose")
    weight = call.get_field("weight")
    symptoms = call.get_field("symptoms")
    med_adherence = call.get_field("medication_adherence")

    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": "Jamie",
        "organization": "Cedar Health",
        "use_case": "chronic_disease_monitoring",
        "patient_name": patient_name,
        "patient_id": patient_id,
        "conditions_monitored": {
            "hypertension": call.has_hypertension,
            "diabetes": call.has_diabetes,
            "weight_management": call.has_weight_management,
        },
        "fields": {
            "blood_pressure_systolic": bp_systolic,
            "blood_pressure_diastolic": bp_diastolic,
            "blood_glucose": glucose,
            "weight": weight,
            "symptoms": symptoms,
            "medication_adherence": med_adherence,
        },
    }
    print(json.dumps(results, indent=2))
    logging.info("Chronic disease monitoring results saved locally.")

    # Post-call: write one Observation per collected metric, each tagged with the
    # correct LOINC code so they appear correctly in Epic's flowsheet and trending views.
    # Readings the patient didn't take today ("not measured") are skipped rather than
    # posted as null values.
    try:
        base_url = os.environ["EPIC_BASE_URL"]
        access_token = os.environ["EPIC_ACCESS_TOKEN"]
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        effective_time = datetime.now(timezone.utc).isoformat()
        subject_ref = {"reference": f"Patient/{patient_id}"}
        observations = []

        # Blood pressure is a composite Observation with systolic and diastolic as components
        if bp_systolic and bp_systolic != "not measured":
            bp_components = [
                {
                    "code": {"coding": [{"system": "http://loinc.org", "code": "8480-6", "display": "Systolic blood pressure"}]},
                    "valueString": str(bp_systolic),
                }
            ]
            if bp_diastolic:
                bp_components.append(
                    {
                        "code": {"coding": [{"system": "http://loinc.org", "code": "8462-4", "display": "Diastolic blood pressure"}]},
                        "valueString": str(bp_diastolic),
                    }
                )
            observations.append({
                "resourceType": "Observation",
                "status": "final",
                "code": {"coding": [{"system": "http://loinc.org", "code": "55284-4", "display": "Blood pressure systolic and diastolic"}]},
                "subject": subject_ref,
                "effectiveDateTime": effective_time,
                "component": bp_components,
            })

        # Blood glucose — only if collected
        if glucose and glucose != "not measured":
            observations.append({
                "resourceType": "Observation",
                "status": "final",
                "code": {"coding": [{"system": "http://loinc.org", "code": "2339-0", "display": "Glucose [Mass/volume] in Blood"}]},
                "subject": subject_ref,
                "effectiveDateTime": effective_time,
                "valueString": str(glucose),
            })

        # Weight — only if collected
        if weight and weight != "not measured":
            observations.append({
                "resourceType": "Observation",
                "status": "final",
                "code": {"coding": [{"system": "http://loinc.org", "code": "29463-7", "display": "Body weight"}]},
                "subject": subject_ref,
                "effectiveDateTime": effective_time,
                "valueString": str(weight),
            })

        # Symptoms and adherence summary — always posted
        observations.append({
            "resourceType": "Observation",
            "status": "final",
            "code": {"coding": [{"system": "http://loinc.org", "code": "72166-2", "display": "Patient-reported health status"}]},
            "subject": subject_ref,
            "effectiveDateTime": effective_time,
            "valueString": f"Symptoms: {symptoms}. Medication adherence: {med_adherence}.",
        })

        for obs in observations:
            resp = requests.post(
                f"{base_url}/Observation",
                headers=headers,
                json=obs,
                timeout=10,
            )
            resp.raise_for_status()
            obs_id = resp.json().get("id", "")
            logging.info("Epic Observation created: %s (%s)", obs_id, obs["code"]["coding"][0]["display"])
    except Exception as e:
        logging.error("Failed to post Epic Observations: %s", e)

    concerning_symptoms = symptoms and symptoms.strip().lower() not in ("none", "none reported", "no")
    if concerning_symptoms:
        call.hangup(
            final_instructions=(
                f"Express concern about the symptoms {patient_name} reported. Let them know "
                "their readings and symptoms have been sent to their care team at Cedar Health "
                "for review. If they experience severe symptoms such as chest pain or difficulty "
                "breathing, advise them to call 911 immediately. Thank them and wish them well."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {patient_name} for completing today's check-in. Let them know their "
                "readings have been sent to their care team at Cedar Health. Remind them to "
                "continue taking their medications as prescribed and to call the clinic if "
                "anything changes. Wish them a great day."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound chronic disease monitoring call for Cedar Health via Epic FHIR."
    )
    parser.add_argument("phone", help="Patient phone number to call (E.164 format, e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Full name of the patient")
    parser.add_argument("--patient-id", required=True, help="Epic Patient FHIR resource ID")
    args = parser.parse_args()

    logging.info(
        "Initiating chronic disease monitoring call to %s (%s), patient ID: %s",
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

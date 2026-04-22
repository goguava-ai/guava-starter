import guava
import os
import logging
from guava import logging_utils
import json
import requests
import argparse
from datetime import datetime, timezone


agent = guava.Agent(
    name="Cameron",
    organization="Cedar Health",
    purpose=(
        "to complete a pre-operative checklist with patients before their surgery "
        "and document their readiness in Epic on behalf of Cedar Health"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")
    call.reach_person(contact_full_name=patient_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    patient_name = call.get_variable("patient_name")
    surgery_date = call.get_variable("surgery_date")
    if outcome == "unavailable":
        call.hangup(
            final_instructions=(
                f"We were unable to reach {patient_name}. Leave a voicemail on behalf of "
                "Cedar Health asking them to call back as soon as possible to complete their "
                f"pre-operative checklist before their surgery on {surgery_date}. "
                "Provide the clinic's main number."
            )
        )
    elif outcome == "available":
        call.set_task(
            "surgery_preop_checkin",
            objective=(
                f"Complete a pre-operative checklist with {patient_name} before their surgery "
                f"at Cedar Health on {surgery_date}. Confirm NPO status, bowel prep, "
                "transport arrangements, and that medications have been held per instructions."
            ),
            checklist=[
                guava.Say(
                    f"Hi {patient_name}, this is Cameron calling from Cedar Health. "
                    f"I'm calling to complete your pre-operative checklist before your surgery "
                    f"scheduled for {surgery_date}. This should only take a few minutes."
                ),
                guava.Field(
                    key="npo_confirmed",
                    description=(
                        "Ask the patient to confirm that they have not eaten or drunk anything "
                        "(including water) after midnight the night before surgery, as instructed. "
                        "Capture 'yes' or 'no'. If no, note what they consumed."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="bowel_prep_completed",
                    description=(
                        "Ask whether the patient has completed their bowel preparation as instructed, "
                        "if it was required for their procedure. If bowel prep was not required, "
                        "capture 'not required'."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="transport_arranged",
                    description=(
                        "Ask whether the patient has arranged for a responsible adult to drive them "
                        "home after the procedure, as they will not be able to drive themselves. "
                        "Capture 'yes' or 'no'."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="medications_held",
                    description=(
                        "Ask whether the patient has held (stopped taking) any medications as "
                        "instructed by their surgeon or anesthesiologist, such as blood thinners "
                        "or diabetes medications. Capture 'yes', 'no', or 'no medications to hold'."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="questions",
                    description=(
                        "Ask if the patient has any questions or concerns about their upcoming surgery. "
                        "Capture their questions. Skip if they have none."
                    ),
                    field_type="text",
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("surgery_preop_checkin")
def on_done(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")
    patient_id = call.get_variable("patient_id")
    surgery_date = call.get_variable("surgery_date")
    npo_confirmed = call.get_field("npo_confirmed")
    bowel_prep = call.get_field("bowel_prep_completed")
    transport = call.get_field("transport_arranged")
    meds_held = call.get_field("medications_held")
    questions = call.get_field("questions")

    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": "Cameron",
        "organization": "Cedar Health",
        "use_case": "surgery_preop_checkin",
        "patient_name": patient_name,
        "patient_id": patient_id,
        "surgery_date": surgery_date,
        "fields": {
            "npo_confirmed": npo_confirmed,
            "bowel_prep_completed": bowel_prep,
            "transport_arranged": transport,
            "medications_held": meds_held,
            "questions": questions,
        },
    }
    print(json.dumps(results, indent=2))
    logging.info("Surgery pre-op checkin results saved locally.")

    # Post-call: encode the checklist responses and upload to Epic as a DocumentReference
    # (LOINC 34745-0: Nurse pre-operative assessment note). The surgical team can pull
    # this directly from the patient's chart before the procedure begins.
    try:
        base_url = os.environ["EPIC_BASE_URL"]
        access_token = os.environ["EPIC_ACCESS_TOKEN"]
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        note_text = (
            f"Pre-operative checklist for {patient_name} — surgery on {surgery_date}\n"
            f"NPO confirmed: {npo_confirmed}\n"
            f"Bowel prep: {bowel_prep}\n"
            f"Transport arranged: {transport}\n"
            f"Medications held: {meds_held}\n"
            f"Patient questions: {questions or 'None'}"
        )
        import base64
        encoded_note = base64.b64encode(note_text.encode()).decode()

        doc_payload = {
            "resourceType": "DocumentReference",
            "status": "current",
            "type": {
                "coding": [
                    {
                        "system": "http://loinc.org",
                        "code": "34745-0",
                        "display": "Nurse pre-operative assessment note",
                    }
                ]
            },
            "subject": {"reference": f"Patient/{patient_id}"},
            "date": datetime.now(timezone.utc).isoformat(),
            "content": [
                {
                    "attachment": {
                        "contentType": "text/plain",
                        "data": encoded_note,
                        "title": f"Pre-op checklist — {patient_name} — {surgery_date}",
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

    # Check for critical pre-op failures that may require same-day clinical intervention.
    # NPO violations and missing transport are the two most common reasons surgeries
    # get cancelled or delayed — surface them immediately.
    transport_ok = transport and transport.strip().lower() == "yes"
    npo_ok = npo_confirmed and npo_confirmed.strip().lower() == "yes"
    issues = []
    if not npo_ok:
        issues.append("NPO status")
    if not transport_ok:
        issues.append("transport arrangements")

    if issues:
        call.hangup(
            final_instructions=(
                f"Express concern about {' and '.join(issues)}. Advise {patient_name} to "
                "contact Cedar Health immediately to speak with their surgical team, as these "
                "issues may affect whether the surgery can proceed as planned. Provide the "
                "clinic's main number. Thank them and wish them well."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Let {patient_name} know their pre-op checklist is complete and they are "
                f"all set for their surgery on {surgery_date}. Remind them to arrive at the "
                "time specified in their instructions and to bring a photo ID and insurance card. "
                "If they had questions, confirm those will be passed to their surgical team. "
                "Wish them well and say goodbye."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound surgery pre-op checkin call for Cedar Health via Epic FHIR."
    )
    parser.add_argument("phone", help="Patient phone number to call (E.164 format, e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Full name of the patient")
    parser.add_argument("--patient-id", required=True, help="Epic Patient FHIR resource ID")
    parser.add_argument("--surgery-date", required=True, help="Surgery date shown to the patient (e.g. 'March 20th at 7:00 AM')")
    args = parser.parse_args()

    logging.info(
        "Initiating surgery pre-op checkin call to %s (%s) for surgery on %s",
        args.name,
        args.phone,
        args.surgery_date,
    )

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "patient_name": args.name,
            "patient_id": args.patient_id,
            "surgery_date": args.surgery_date,
        },
    )

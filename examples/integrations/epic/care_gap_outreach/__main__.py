import argparse
import json
import logging
import os
from datetime import datetime, timezone

import guava
import requests
from guava import logging_utils

agent = guava.Agent(
    name="Morgan",
    organization="Cedar Health",
    purpose=(
        "to reach out about an overdue preventive care service and help the patient schedule it on behalf of Cedar Health"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")
    call.reach_person(contact_full_name=patient_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    patient_name = call.get_variable("patient_name")
    care_gap = call.get_variable("care_gap")
    if outcome == "unavailable":
        call.hangup(
            final_instructions=(
                f"We were unable to reach {patient_name}. Leave a brief, friendly voicemail on "
                "behalf of Cedar Health letting them know we called about an overdue preventive care "
                f"service — {care_gap} — and asking them to call back to schedule."
            )
        )
    elif outcome == "available":
        call.set_task(
            "care_gap_outreach",
            objective=(
                f"Inform {patient_name} that they are due for {care_gap} and encourage "
                "them to schedule it. Capture their interest in scheduling and preferred timing."
            ),
            checklist=[
                guava.Say(
                    f"Hi {patient_name}, this is Morgan calling from Cedar Health. "
                    f"I'm reaching out because our records show you may be due for {care_gap}, "
                    "which is an important part of your preventive care."
                ),
                guava.Field(
                    key="interested_in_scheduling",
                    description=(
                        f"Ask whether the patient is interested in scheduling their {care_gap} "
                        "at Cedar Health. Capture 'yes', 'no', or 'already scheduled'."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="preferred_timeframe",
                    description=(
                        "If the patient wants to schedule, ask what timeframe works best for them — "
                        "for example, within the next two weeks, next month, or a specific date. "
                        "Skip if they declined or said already scheduled."
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="questions",
                    description=(
                        "Ask if the patient has any questions about the care service or why it is recommended. "
                        "Capture any questions they have. Skip if they have none."
                    ),
                    field_type="text",
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("care_gap_outreach")
def on_done(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")
    patient_id = call.get_variable("patient_id")
    care_gap = call.get_variable("care_gap")
    interested = call.get_field("interested_in_scheduling")
    preferred_timeframe = call.get_field("preferred_timeframe")
    questions = call.get_field("questions")

    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": "Morgan",
        "organization": "Cedar Health",
        "use_case": "care_gap_outreach",
        "patient_name": patient_name,
        "patient_id": patient_id,
        "care_gap": care_gap,
        "fields": {
            "interested_in_scheduling": interested,
            "preferred_timeframe": preferred_timeframe,
            "questions": questions,
        },
    }
    print(json.dumps(results, indent=2))
    logging.info("Care gap outreach results saved locally.")

    # Post-call: write a CommunicationRequest to Epic to record the outreach outcome.
    # Status "completed" signals this gap has been addressed so it doesn't trigger
    # another outreach cycle. The payload captures intent and scheduling preferences
    # for the care coordination team to act on.
    try:
        base_url = os.environ["EPIC_BASE_URL"]
        access_token = os.environ["EPIC_ACCESS_TOKEN"]
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        comm_req_payload = {
            "resourceType": "CommunicationRequest",
            "status": "completed",
            "subject": {"reference": f"Patient/{patient_id}"},
            "authoredOn": datetime.now(timezone.utc).isoformat(),
            "payload": [
                {
                    "contentString": (
                        f"Care gap outreach for: {care_gap}. "
                        f"Patient response: {interested}. "
                        f"Preferred timeframe: {preferred_timeframe or 'Not specified'}. "
                        f"Questions: {questions or 'None'}."
                    )
                }
            ],
        }

        resp = requests.post(
            f"{base_url}/CommunicationRequest",
            headers=headers,
            json=comm_req_payload,
            timeout=10,
        )
        resp.raise_for_status()
        cr_id = resp.json().get("id", "")
        logging.info("Epic CommunicationRequest created: %s", cr_id)
    except Exception as e:
        logging.error("Failed to create Epic CommunicationRequest: %s", e)

    # Branch the closing message across three outcomes: wants to schedule,
    # already has it scheduled, or declined — each gets a tailored response.
    wants_to_schedule = interested and interested.strip().lower() == "yes"
    already_scheduled = interested and "already" in interested.strip().lower()

    if wants_to_schedule:
        call.hangup(
            final_instructions=(
                f"Let {patient_name} know that a scheduling coordinator at Cedar Health will "
                f"follow up to book their {care_gap} appointment within the next business day. "
                "If they had questions, confirm those will be passed along to their care team. "
                "Thank them for their time and wish them a great day."
            )
        )
    elif already_scheduled:
        call.hangup(
            final_instructions=(
                f"Acknowledge that {patient_name} already has this scheduled — that is great news. "
                "Thank them for staying on top of their preventive care and wish them a great day."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Respect {patient_name}'s decision. Let them know Cedar Health is here whenever "
                f"they are ready to schedule their {care_gap}. Provide the clinic's main number "
                "and wish them a great day."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound care gap outreach call for Cedar Health via Epic FHIR."
    )
    parser.add_argument("phone", help="Patient phone number to call (E.164 format, e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Full name of the patient")
    parser.add_argument("--patient-id", required=True, help="Epic Patient FHIR resource ID")
    parser.add_argument(
        "--care-gap",
        required=True,
        help="Description of the care gap (e.g. 'annual wellness visit', 'colorectal cancer screening')",
    )
    args = parser.parse_args()

    logging.info(
        "Initiating care gap outreach call to %s (%s) for: %s",
        args.name,
        args.phone,
        args.care_gap,
    )

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "patient_name": args.name,
            "patient_id": args.patient_id,
            "care_gap": args.care_gap,
        },
    )

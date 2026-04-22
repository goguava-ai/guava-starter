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


def post_communication_request(patient_id: str, care_gap: str, intent: str, headers: dict) -> bool:
    base_url = os.environ["ECW_BASE_URL"]
    payload = {
        "resourceType": "CommunicationRequest",
        "status": "active",
        "subject": {"reference": f"Patient/{patient_id}"},
        "reasonCode": [{"text": f"Care gap outreach: {care_gap}"}],
        "note": [{"text": f"Patient scheduling intent: {intent}"}],
    }
    resp = requests.post(f"{base_url}/CommunicationRequest", headers=headers, json=payload, timeout=10)
    return resp.ok


agent = guava.Agent(
    name="Sam",
    organization="Sunrise Family Practice",
    purpose="to reach out to patients who are overdue for preventive care and help them schedule",
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
    call.headers = headers

    call.reach_person(contact_full_name=patient_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    patient_name = call.get_variable("patient_name")
    care_gap = call.get_variable("care_gap")
    if outcome == "unavailable":
        logging.info("Unable to reach %s for care gap outreach.", patient_name)
        call.hangup(
            final_instructions=(
                f"Leave a brief, warm voicemail for {patient_name} from Sunrise Family Practice. "
                f"Let them know you're calling because they may be due for a {care_gap} "
                "and invite them to call back to schedule. Keep it friendly and non-alarming."
            )
        )
    elif outcome == "available":
        call.set_task(
            "care_gap_outreach",
            objective=(
                f"Call {patient_name} who is due for a {care_gap}. "
                "Educate them on the importance, address any concerns, and gauge their intent to schedule."
            ),
            checklist=[
                guava.Say(
                    f"Hi {patient_name}, this is Sam calling from Sunrise Family Practice. "
                    f"I'm reaching out because our records show you may be due for a {care_gap}. "
                    "We just wanted to give you a friendly reminder — these visits are an important "
                    "part of staying on top of your health."
                ),
                guava.Field(
                    key="aware",
                    field_type="multiple_choice",
                    description=f"Ask if they were aware they were due for a {care_gap}.",
                    choices=["yes", "no"],
                    required=True,
                ),
                guava.Field(
                    key="barriers",
                    field_type="multiple_choice",
                    description="Ask if there are any barriers preventing them from coming in.",
                    choices=["no barriers", "scheduling difficulty", "cost concerns", "feeling well / no symptoms", "other"],
                    required=True,
                ),
                guava.Field(
                    key="scheduling_intent",
                    field_type="multiple_choice",
                    description="Ask if they'd like to schedule today or have someone follow up.",
                    choices=["yes, schedule now", "follow up later", "not interested"],
                    required=True,
                ),
            ],
        )


@agent.on_task_complete("care_gap_outreach")
def on_done(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")
    patient_id = call.get_variable("patient_id")
    care_gap = call.get_variable("care_gap")
    intent = call.get_field("scheduling_intent") or ""
    barriers = call.get_field("barriers") or ""

    logging.info(
        "Care gap outreach for patient %s — gap: %s, intent: %s, barriers: %s",
        patient_id, care_gap, intent, barriers,
    )

    try:
        post_communication_request(patient_id, care_gap, intent, call.headers)
    except Exception as e:
        logging.error("Failed to post CommunicationRequest: %s", e)

    if "schedule now" in intent:
        call.hangup(
            final_instructions=(
                f"Let {patient_name} know that a scheduling coordinator will call them "
                "back within one business day to find a time that works. "
                "Thank them for their commitment to their health and wish them a great day."
            )
        )
    elif "follow up" in intent:
        call.hangup(
            final_instructions=(
                f"Thank {patient_name} for their time. Let them know we'll reach out "
                "again in the near future to help schedule. They can also call the office anytime. "
                "Wish them a great day."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Respect {patient_name}'s decision. Let them know we're always here "
                "if they change their mind. Thank them for taking the call and wish them well."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(description="Outbound care gap outreach via eClinicalWorks FHIR.")
    parser.add_argument("phone", help="Patient phone number (E.164)")
    parser.add_argument("--name", required=True)
    parser.add_argument("--patient-id", required=True)
    parser.add_argument("--care-gap", required=True, help="Care gap description (e.g. 'annual wellness visit')")
    args = parser.parse_args()

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "patient_name": args.name,
            "patient_id": args.patient_id,
            "care_gap": args.care_gap,
        },
    )

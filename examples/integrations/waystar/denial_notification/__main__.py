import argparse
import json
import logging
import os
from datetime import datetime, timezone

import guava
import requests
from guava import logging_utils

WAYSTAR_CLIENT_ID = os.environ["WAYSTAR_CLIENT_ID"]
WAYSTAR_CLIENT_SECRET = os.environ["WAYSTAR_CLIENT_SECRET"]
WAYSTAR_BASE_URL = os.environ.get("WAYSTAR_BASE_URL", "https://api.waystar.com")


def get_access_token() -> str:
    resp = requests.post(
        f"{WAYSTAR_BASE_URL}/auth/oauth2/token",
        data={
            "grant_type": "client_credentials",
            "client_id": WAYSTAR_CLIENT_ID,
            "client_secret": WAYSTAR_CLIENT_SECRET,
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def get_claim_detail(claim_id: str) -> dict | None:
    """Fetches the full claim detail from Waystar by claim ID."""
    token = get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    resp = requests.get(
        f"{WAYSTAR_BASE_URL}/claims/v1/{claim_id}",
        headers=headers,
        timeout=10,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def update_claim_followup_status(claim_id: str, outcome: str) -> None:
    """Records the patient notification outcome on the claim in Waystar."""
    token = get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    requests.patch(
        f"{WAYSTAR_BASE_URL}/claims/v1/{claim_id}",
        headers=headers,
        json={
            "workflowStatus": "patient_notified",
            "notes": f"Patient notified of denial on {datetime.now(timezone.utc).strftime('%Y-%m-%d')}: {outcome}",
        },
        timeout=10,
    )


agent = guava.Agent(
    name="Alex",
    organization="Riverside Family Medicine Billing",
    purpose=(
        "to notify patients about insurance claim denials and help them understand "
        "their options for next steps"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")
    call.reach_person(contact_full_name=patient_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    patient_name = call.get_variable("patient_name")
    claim_id = call.get_variable("claim_id")
    service_date = call.get_variable("service_date")

    if outcome == "unavailable":
        logging.info(
            "Unable to reach %s for denial notification on claim %s",
            patient_name, claim_id,
        )
        call.hangup(
            final_instructions=(
                f"Leave a professional voicemail for {patient_name} from Riverside Family "
                "Medicine billing. Let them know this call is regarding an insurance claim "
                f"from {service_date} and ask them to call back at their earliest "
                "convenience. Provide the billing department callback number. "
                "Keep the message brief and professional — do not mention the word 'denial'."
            )
        )
    elif outcome == "available":
        first_name = patient_name.split()[0] if patient_name else "there"
        service_description = call.get_variable("service_description")
        claim_amount = call.get_variable("claim_amount")
        denial_reason = call.get_variable("denial_reason")

        call.set_task(
            "record_outcome",
            objective=(
                f"Notify {patient_name} that their insurance claim for "
                f"'{service_description}' on {service_date} was denied. "
                "Explain the denial reason and gather their preferred next step."
            ),
            checklist=[
                guava.Say(
                    f"Hi {first_name}, this is Alex calling from Riverside Family Medicine "
                    "billing. I'm calling with an important update about an insurance claim "
                    f"for your visit on {service_date}."
                ),
                guava.Field(
                    key="understood_denial",
                    field_type="multiple_choice",
                    description=(
                        f"Explain that insurance claim {claim_id} for "
                        f"'{service_description}' (${claim_amount}) was denied "
                        f"with the reason: '{denial_reason}'. Ask if they understand "
                        "and would like to hear their options."
                    ),
                    choices=["yes, please explain my options", "no, I have questions first"],
                    required=True,
                ),
                guava.Field(
                    key="preferred_next_step",
                    field_type="multiple_choice",
                    description=(
                        "Explain the options: we can file an appeal with the insurance company, "
                        "they can contact their insurance company directly, or they can arrange "
                        "to pay the balance directly. Ask which they prefer."
                    ),
                    choices=[
                        "file an appeal on my behalf",
                        "I will contact my insurance company",
                        "arrange self-pay",
                        "I need more time to decide",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="additional_questions",
                    field_type="text",
                    description=(
                        "Ask if they have any other questions about the denial or the billing "
                        "process. Capture any concerns they raise."
                    ),
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("record_outcome")
def on_done(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")
    claim_id = call.get_variable("claim_id")
    denial_reason = call.get_variable("denial_reason")
    service_description = call.get_variable("service_description")
    service_date = call.get_variable("service_date")
    claim_amount = call.get_variable("claim_amount")
    next_step = call.get_field("preferred_next_step")
    questions = call.get_field("additional_questions") or ""
    first_name = patient_name.split()[0] if patient_name else "there"

    logging.info(
        "Denial notification outcome for claim %s: next_step=%s",
        claim_id, next_step,
    )

    outcome = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": "Alex",
        "use_case": "denial_notification",
        "patient_name": patient_name,
        "claim_id": claim_id,
        "denial_reason": denial_reason,
        "service_description": service_description,
        "service_date": service_date,
        "claim_amount": claim_amount,
        "preferred_next_step": next_step,
        "additional_questions": questions,
    }
    print(json.dumps(outcome, indent=2))

    try:
        update_claim_followup_status(claim_id, next_step)
        logging.info("Waystar claim %s updated with notification outcome", claim_id)
    except Exception as e:
        logging.warning("Failed to update Waystar claim status: %s", e)

    if next_step == "file an appeal on my behalf":
        call.hangup(
            final_instructions=(
                f"Let {first_name} know that we will file an appeal with their insurance "
                "company on their behalf. The appeal process typically takes 30 to 60 days. "
                "Let them know our billing team will contact them with an update. "
                "Thank them for letting us handle this."
            )
        )
    elif next_step == "arrange self-pay":
        call.hangup(
            final_instructions=(
                f"Let {first_name} know that our billing team will send them a statement "
                f"for the balance of ${claim_amount}. "
                "Let them know payment plan options may be available and they can discuss "
                "those with our billing department. Provide the billing department number. "
                "Thank them for their time."
            )
        )
    elif next_step == "I will contact my insurance company":
        call.hangup(
            final_instructions=(
                f"Encourage {first_name} to contact their insurance company and reference "
                f"claim number {claim_id}. Let them know our billing team is available "
                "if they need documentation or additional information for the appeal. "
                "Thank them for calling and wish them success with the appeal."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Let {first_name} know there's no rush and our billing team will follow "
                "up with them by mail with their options in writing. "
                "Reassure them that no immediate action is required right now. "
                "Thank them for their time."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound call to notify a patient of an insurance claim denial."
    )
    parser.add_argument("phone", help="Patient phone number (E.164, e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Patient full name")
    parser.add_argument("--claim-id", required=True, help="Waystar claim ID")
    parser.add_argument("--denial-reason", required=True, help="Denial reason description")
    parser.add_argument("--service", required=True, help="Service or procedure description")
    parser.add_argument("--service-date", required=True, help="Date of service (YYYY-MM-DD)")
    parser.add_argument("--amount", required=True, help="Claim amount (e.g. 350.00)")
    args = parser.parse_args()

    logging.info(
        "Initiating denial notification call to %s for claim %s",
        args.name, args.claim_id,
    )

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "patient_name": args.name,
            "claim_id": args.claim_id,
            "denial_reason": args.denial_reason,
            "service_description": args.service,
            "service_date": args.service_date,
            "claim_amount": args.amount,
        },
    )

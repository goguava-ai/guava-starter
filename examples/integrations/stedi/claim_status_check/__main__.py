import logging
import os
import random

import guava
import requests
from guava import logging_utils

STEDI_API_KEY = os.environ["STEDI_API_KEY"]
PROVIDER_NPI = os.environ["STEDI_PROVIDER_NPI"]
PROVIDER_NAME = os.environ.get("STEDI_PROVIDER_NAME", "Ridgeline Health")
BASE_URL = "https://healthcare.us.stedi.com/2024-04-01"
HEADERS = {
    "Authorization": f"Key {STEDI_API_KEY}",
    "Content-Type": "application/json",
}

# X12 277 status category codes → human-readable descriptions
STATUS_CATEGORY_DESCRIPTIONS: dict[str, str] = {
    "A0": "forwarded to another entity for additional processing",
    "A1": "processed — no further information is available at this time",
    "A2": "processed — final",
    "A3": "processed — payer is requesting additional information",
    "A6": "rejected — could not be processed",
    "A7": "denied — payment will not be made",
    "A8": "pended — awaiting additional information from the provider",
    "DR": "identified as a duplicate of a previously submitted claim",
    "F1": "finalized",
    "F2": "finalized — payment has been issued",
    "F3": "finalized — payment is pending",
    "F4": "finalized — denied",
}


def check_claim_status(
    trading_partner_id: str,
    member_id: str,
    first_name: str,
    last_name: str,
    date_of_birth: str,
    patient_control_number: str,
) -> dict:
    """Posts a real-time claim status inquiry (276/277) to Stedi and returns the response."""
    payload = {
        "controlNumber": str(random.randint(100000000, 999999999)),
        "tradingPartnerServiceId": trading_partner_id,
        "provider": {
            "organizationName": PROVIDER_NAME,
            "npi": PROVIDER_NPI,
        },
        "subscriber": {
            "memberId": member_id,
            "firstName": first_name.upper(),
            "lastName": last_name.upper(),
            "dateOfBirth": date_of_birth.replace("-", ""),
        },
        "claim": {
            "claimFilingCode": "CI",
            "patientControlNumber": patient_control_number,
        },
    }
    resp = requests.post(
        f"{BASE_URL}/change/medicalnetwork/claimstatus/v2",
        headers=HEADERS,
        json=payload,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def summarize_claim_status(response: dict) -> str:
    """Returns a human-readable status description from a 277 claim status response."""
    claim_statuses = response.get("claimStatus", [])
    if not claim_statuses:
        return "no status information is currently available for this claim"

    status = claim_statuses[0]
    category_code = status.get("statusCategoryCode", "")
    description = (
        status.get("statusCategoryCodeValue")
        or STATUS_CATEGORY_DESCRIPTIONS.get(category_code, "status unknown")
    )

    adjudicated_date = status.get("adjudicationFinalizedDate", "")
    check_number = status.get("checkNumber", "")
    check_date = status.get("checkDate", "")

    if adjudicated_date:
        description += f", finalized on {adjudicated_date}"
    if check_number and check_date:
        description += f", payment check #{check_number} issued on {check_date}"

    return description


agent = guava.Agent(
    name="Sam",
    organization="Ridgeline Health",
    purpose=(
        "to help patients and their families check the status of insurance claims "
        "submitted on their behalf"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "look_up_claim",
        objective=(
            "A patient has called to find out what happened to a claim. "
            "Verify their identity, collect their claim reference number, "
            "and look up the real-time claim status through Stedi."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling Ridgeline Health billing. I'm Sam. "
                "I can look up the status of a claim for you right now."
            ),
            guava.Field(
                key="first_name",
                field_type="text",
                description="Ask for the patient's first name.",
                required=True,
            ),
            guava.Field(
                key="last_name",
                field_type="text",
                description="Ask for the patient's last name.",
                required=True,
            ),
            guava.Field(
                key="date_of_birth",
                field_type="date",
                description="Ask for their date of birth.",
                required=True,
            ),
            guava.Field(
                key="member_id",
                field_type="text",
                description="Ask for their insurance member ID.",
                required=True,
            ),
            guava.Field(
                key="payer_id",
                field_type="text",
                description="Ask which insurance company processed the claim.",
                required=True,
            ),
            guava.Field(
                key="claim_number",
                field_type="text",
                description=(
                    "Ask for the claim reference number from their Explanation of Benefits "
                    "or billing statement. This is sometimes labeled 'patient control number' "
                    "or 'patient account number'."
                ),
                required=True,
            ),
        ],
    )


@agent.on_task_complete("look_up_claim")
def look_up_claim(call: guava.Call) -> None:
    first_name = call.get_field("first_name") or ""
    last_name = call.get_field("last_name") or ""
    dob = call.get_field("date_of_birth") or ""
    member_id = call.get_field("member_id") or ""
    payer_id = call.get_field("payer_id") or ""
    claim_number = call.get_field("claim_number") or ""

    logging.info(
        "Checking claim status — patient: %s %s, claim: %s, payer: %s",
        first_name, last_name, claim_number, payer_id,
    )

    try:
        result = check_claim_status(
            payer_id, member_id, first_name, last_name, dob, claim_number
        )
        status_description = summarize_claim_status(result)
    except Exception as e:
        logging.error("Stedi claim status check failed: %s", e)
        call.hangup(
            final_instructions=(
                f"Apologize to {first_name} — there was a technical issue checking their claim. "
                "Ask them to call back during business hours so a billing specialist can assist. "
                "Thank them for their patience."
            )
        )
        return

    logging.info("Claim status for #%s: %s", claim_number, status_description)

    call.hangup(
        final_instructions=(
            f"Let {first_name} know the current status of claim #{claim_number}: "
            f"it is {status_description}. "
            "If they want to follow up, dispute a denial, or ask about a specific amount, "
            "let them know they can speak with a billing specialist by calling back. "
            "Thank them for calling Ridgeline Health."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])

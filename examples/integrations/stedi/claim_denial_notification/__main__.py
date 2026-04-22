import guava
import os
import logging
from guava import logging_utils
import argparse
import random
import requests


STEDI_API_KEY = os.environ["STEDI_API_KEY"]
PROVIDER_NPI = os.environ["STEDI_PROVIDER_NPI"]
PROVIDER_NAME = os.environ.get("STEDI_PROVIDER_NAME", "Ridgeline Health")
BASE_URL = "https://healthcare.us.stedi.com/2024-04-01"
HEADERS = {
    "Authorization": f"Key {STEDI_API_KEY}",
    "Content-Type": "application/json",
}

# Status category codes that indicate a claim was denied or rejected
DENIED_STATUS_CODES = {"A6", "A7", "F4"}

STATUS_DESCRIPTIONS: dict[str, str] = {
    "A6": "rejected — the claim could not be processed",
    "A7": "denied — the payer will not be making payment",
    "F4": "finalized as denied",
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


def get_denial_details(response: dict) -> tuple[bool, str, str]:
    """Returns (is_denied, status_code, denial_description) from a claim status response."""
    for status in response.get("claimStatus", []):
        category_code = status.get("statusCategoryCode", "")
        if category_code in DENIED_STATUS_CODES:
            description = (
                status.get("statusCategoryCodeValue")
                or STATUS_DESCRIPTIONS.get(category_code, "denied")
            )
            return True, category_code, description
    return False, "", ""


agent = guava.Agent(
    name="Taylor",
    organization="Ridgeline Health",
    purpose=(
        "to inform patients about insurance claim decisions and help them understand "
        "their options, including how to appeal a denial"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")
    first_name = call.get_variable("first_name")
    last_name = call.get_variable("last_name")
    date_of_birth = call.get_variable("date_of_birth")
    member_id = call.get_variable("member_id")
    payer_id = call.get_variable("payer_id")
    claim_number = call.get_variable("claim_number")
    service_description = call.get_variable("service_description")

    # Check the claim status before calling so we only place the call if it's actually denied.
    is_denied = False
    denial_description = ""
    try:
        result = check_claim_status(
            payer_id, member_id, first_name, last_name, date_of_birth, claim_number
        )
        is_denied, _, denial_description = get_denial_details(result)
        logging.info(
            "Pre-call claim check for #%s — denied: %s, reason: %s",
            claim_number, is_denied, denial_description,
        )
    except Exception as e:
        logging.error("Pre-call claim status check failed for #%s: %s", claim_number, e)
        is_denied = False

    call.is_denied = is_denied
    call.denial_description = denial_description

    call.reach_person(contact_full_name=patient_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    patient_name = call.get_variable("patient_name")
    claim_number = call.get_variable("claim_number")
    service_description = call.get_variable("service_description")

    if outcome == "unavailable":
        logging.info(
            "Unable to reach %s for claim denial notification (claim #%s)",
            patient_name, claim_number,
        )
        call.hangup(
            final_instructions=(
                f"Leave a brief, professional voicemail for {patient_name} on behalf of "
                "Ridgeline Health billing. Let them know you're calling about a claim decision "
                f"on claim #{claim_number} for {service_description} and ask them "
                "to call back at their convenience to discuss next steps. "
                "Keep it concise and non-alarming."
            )
        )
    elif outcome == "available":
        if not call.is_denied:
            # Claim is not (or no longer) denied — no action needed
            logging.info(
                "Claim #%s is not in a denied state for %s — ending call",
                claim_number, patient_name,
            )
            call.hangup(
                final_instructions=(
                    f"Greet {patient_name} from Ridgeline Health. "
                    f"Let them know you were calling about claim #{claim_number} for "
                    f"{service_description}, but it looks like it's no longer showing "
                    "as denied in our system. Apologize for any confusion and let them know "
                    "their billing team will send an updated summary by mail. Thank them."
                )
            )
            return

        call.set_task(
            "handle_next_steps",
            objective=(
                f"Inform {patient_name} that their insurance claim #{claim_number} "
                f"for {service_description} was denied, explain why, and help them "
                "decide on next steps."
            ),
            checklist=[
                guava.Say(
                    f"Hi {patient_name}, this is Taylor calling from Ridgeline Health billing. "
                    f"I'm calling about your insurance claim #{claim_number} for "
                    f"{service_description}. Unfortunately, your insurance company has "
                    f"issued a decision of: {call.denial_description}. "
                    "I know this isn't the news you were hoping for, and I want to help you "
                    "understand your options."
                ),
                guava.Field(
                    key="has_questions",
                    field_type="multiple_choice",
                    description=(
                        "Ask if they'd like to know more about why it was denied, "
                        "or if they're ready to discuss what they can do next."
                    ),
                    choices=["tell me why it was denied", "what are my options"],
                    required=True,
                ),
                guava.Field(
                    key="next_step_preference",
                    field_type="multiple_choice",
                    description=(
                        "Ask how they'd like to proceed. Options: file an appeal with the insurer, "
                        "have our billing team review, set up a payment plan, or get a call-back "
                        "from a billing specialist."
                    ),
                    choices=[
                        "file an appeal",
                        "have billing review",
                        "set up a payment plan",
                        "call me back with billing",
                    ],
                    required=True,
                ),
            ],
        )


@agent.on_task_complete("handle_next_steps")
def handle_next_steps(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")
    claim_number = call.get_variable("claim_number")
    next_step = call.get_field("next_step_preference") or ""
    logging.info(
        "Denial next step for %s (claim #%s): %s",
        patient_name, claim_number, next_step,
    )

    if "appeal" in next_step:
        call.hangup(
            final_instructions=(
                f"Let {patient_name} know that filing an appeal is their right. "
                "Explain that our billing team will prepare an appeal letter on their behalf "
                "and submit it to the insurer — this typically takes 5–7 business days. "
                "Let them know they'll receive a written notice from us with the appeal details. "
                "Thank them for their patience and for working with us on this."
            )
        )
    elif "payment plan" in next_step:
        call.hangup(
            final_instructions=(
                f"Let {patient_name} know our billing team will reach out within two "
                "business days to set up a payment plan that works for their situation. "
                "Assure them we have flexible options available. "
                "Thank them for their understanding."
            )
        )
    elif "billing review" in next_step:
        call.hangup(
            final_instructions=(
                f"Let {patient_name} know a billing specialist will review their claim "
                "and call them back within one business day with findings. "
                "Thank them for their patience."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Let {patient_name} know a billing specialist will call them back "
                "within one business day to walk through all available options. "
                "Provide Ridgeline Health's billing phone number if asked. "
                "Thank them for taking the time to speak with us."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound call to notify a patient of an insurance claim denial."
    )
    parser.add_argument("phone", help="Patient phone number (E.164, e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Patient's full name")
    parser.add_argument("--first-name", required=True, help="Patient's first name")
    parser.add_argument("--last-name", required=True, help="Patient's last name")
    parser.add_argument("--dob", required=True, help="Date of birth (YYYY-MM-DD)")
    parser.add_argument("--member-id", required=True, help="Insurance member ID")
    parser.add_argument("--payer-id", required=True, help="Stedi trading partner ID")
    parser.add_argument("--claim-number", required=True, help="Patient control number / claim ID")
    parser.add_argument(
        "--service",
        required=True,
        help="Human-readable description of the service (e.g. 'your March 10th office visit')",
    )
    args = parser.parse_args()

    logging.info(
        "Initiating claim denial notification call to %s (%s) for claim #%s",
        args.name, args.phone, args.claim_number,
    )

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "patient_name": args.name,
            "first_name": args.first_name,
            "last_name": args.last_name,
            "date_of_birth": args.dob,
            "member_id": args.member_id,
            "payer_id": args.payer_id,
            "claim_number": args.claim_number,
            "service_description": args.service,
        },
    )

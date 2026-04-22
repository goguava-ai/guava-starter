import logging
import os

import guava
import requests
from guava import logging_utils

AVAILITY_CLIENT_ID = os.environ["AVAILITY_CLIENT_ID"]
AVAILITY_CLIENT_SECRET = os.environ["AVAILITY_CLIENT_SECRET"]
AVAILITY_PROVIDER_ID = os.environ["AVAILITY_PROVIDER_ID"]
AVAILITY_PAYER_ID = os.environ.get("AVAILITY_PAYER_ID", "")

BASE_URL = "https://api.availity.com/availity/v1"
TOKEN_URL = f"{BASE_URL}/token"


def get_access_token() -> str:
    resp = requests.post(
        TOKEN_URL,
        auth=(AVAILITY_CLIENT_ID, AVAILITY_CLIENT_SECRET),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "client_credentials", "scope": "hipaa"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def check_eligibility(
    token: str,
    member_id: str,
    date_of_birth: str,
    payer_id: str,
    service_type_code: str = "30",  # 30 = Health Benefit Plan Coverage
) -> dict:
    """
    Submit an eligibility inquiry (270/271) to Availity.
    Returns the coverage response object.
    """
    payload = {
        "memberId": member_id,
        "dateOfBirth": date_of_birth,
        "payerId": payer_id,
        "providerId": AVAILITY_PROVIDER_ID,
        "serviceTypeCode": service_type_code,
    }
    resp = requests.post(
        f"{BASE_URL}/coverages",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def summarize_eligibility(coverage: dict) -> str:
    """Return a spoken-language summary of the eligibility response."""
    status = coverage.get("subscriberStatus") or coverage.get("status") or "unknown"
    plan_name = coverage.get("planDescription") or coverage.get("groupDescription") or ""
    effective_date = coverage.get("planBeginDate") or ""
    term_date = coverage.get("planEndDate") or ""

    parts = [f"Their insurance status is: {status}."]
    if plan_name:
        parts.append(f"Plan name: {plan_name}.")
    if effective_date:
        parts.append(f"Coverage effective date: {effective_date}.")
    if term_date:
        parts.append(f"Coverage end date: {term_date}.")
    return " ".join(parts)


agent = guava.Agent(
    name="Jordan",
    organization="Greenfield Medical Group",
    purpose=(
        "to help patients and front-desk staff at Greenfield Medical Group verify "
        "insurance eligibility before appointments"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "eligibility_verification",
        objective=(
            "A caller needs to verify insurance eligibility. Collect the patient's "
            "member ID, date of birth, and payer information, then check eligibility "
            "through Availity."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling Greenfield Medical Group. This is Jordan. "
                "I can verify insurance eligibility for you. "
                "Please have the patient's insurance card ready."
            ),
            guava.Field(
                key="patient_name",
                field_type="text",
                description="Ask for the patient's full name.",
                required=True,
            ),
            guava.Field(
                key="member_id",
                field_type="text",
                description=(
                    "Ask for the patient's member ID as it appears on their insurance card."
                ),
                required=True,
            ),
            guava.Field(
                key="date_of_birth",
                field_type="text",
                description=(
                    "Ask for the patient's date of birth in MM/DD/YYYY format."
                ),
                required=True,
            ),
            guava.Field(
                key="payer_name",
                field_type="text",
                description=(
                    "Ask for the name of the insurance company or payer — "
                    "for example, Aetna, UnitedHealthcare, Blue Cross Blue Shield."
                ),
                required=True,
            ),
            guava.Field(
                key="service_type",
                field_type="multiple_choice",
                description="Ask what type of service this eligibility check is for.",
                choices=[
                    "general health plan coverage",
                    "primary care visit",
                    "specialist visit",
                    "mental health",
                    "preventive care",
                    "other",
                ],
                required=False,
            ),
        ],
    )


@agent.on_task_complete("eligibility_verification")
def on_done(call: guava.Call) -> None:
    patient_name = call.get_field("patient_name") or "the patient"
    member_id = (call.get_field("member_id") or "").strip()
    dob = (call.get_field("date_of_birth") or "").strip()
    payer_name = call.get_field("payer_name") or ""

    service_type_map = {
        "general health plan coverage": "30",
        "primary care visit": "98",
        "specialist visit": "96",
        "mental health": "MH",
        "preventive care": "98",
        "other": "30",
    }
    service_type_spoken = call.get_field("service_type") or "general health plan coverage"
    service_code = service_type_map.get(service_type_spoken, "30")

    payer_id = AVAILITY_PAYER_ID  # In production, resolve payer_name to payer ID via a lookup table.

    logging.info(
        "Verifying eligibility for %s — member_id: %s, payer: %s",
        patient_name, member_id, payer_name,
    )

    try:
        token = get_access_token()
        coverage = check_eligibility(
            token=token,
            member_id=member_id,
            date_of_birth=dob,
            payer_id=payer_id,
            service_type_code=service_code,
        )
        summary = summarize_eligibility(coverage)
        logging.info("Eligibility result for %s: %s", patient_name, summary)

        call.hangup(
            final_instructions=(
                f"Share the eligibility results for {patient_name} with the caller. "
                f"{summary} "
                "If the patient is active and covered, confirm it warmly. "
                "If there's an issue (terminated, inactive, not found), be empathetic and "
                "suggest the patient contact their insurer or bring their card to the appointment. "
                "Thank them for calling Greenfield Medical Group."
            )
        )
    except requests.HTTPError as e:
        status_code = e.response.status_code if e.response else 0
        if status_code == 404:
            logging.warning("No coverage found for member_id %s", member_id)
            call.hangup(
                final_instructions=(
                    f"Let the caller know that no active coverage was found for {patient_name} "
                    f"with member ID {member_id} at {payer_name}. "
                    "Suggest they double-check the member ID and payer name, or have the patient "
                    "contact their insurance company directly. "
                    "Thank them for calling."
                )
            )
        else:
            logging.error("Availity eligibility check failed (%s): %s", status_code, e)
            call.hangup(
                final_instructions=(
                    "Apologize — the eligibility system returned an error. "
                    "Let the caller know they may need to verify manually through the "
                    "Availity portal or contact the payer directly. "
                    "Thank them for their patience."
                )
            )
    except Exception as e:
        logging.error("Eligibility verification failed: %s", e)
        call.hangup(
            final_instructions=(
                "Apologize for a technical issue with the eligibility check. "
                "Let the caller know they can verify manually through the Availity portal "
                "or by calling the payer directly. Thank them for calling."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])

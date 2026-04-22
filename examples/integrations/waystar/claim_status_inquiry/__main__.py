import guava
import os
import logging
from guava import logging_utils
import json
import requests
from datetime import datetime, timezone


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


def get_claim_status(
    payer_id: str,
    provider_npi: str,
    member_id: str,
    patient_last_name: str,
    patient_dob: str,
    service_date: str,
    claim_number: str | None = None,
) -> dict:
    """Queries Waystar for claim status. Claim number is optional if lookup is by member + service date."""
    token = get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "payerId": payer_id,
        "provider": {
            "npi": provider_npi,
            "organizationName": "Riverside Family Medicine",
        },
        "subscriber": {
            "memberId": member_id,
            "lastName": patient_last_name,
            "dateOfBirth": patient_dob,
        },
        "claimServiceDate": service_date,
    }
    if claim_number:
        payload["claimNumber"] = claim_number

    resp = requests.post(
        f"{WAYSTAR_BASE_URL}/claimstatus/v1/inquiries",
        headers=headers,
        json=payload,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def parse_status_response(response: dict) -> dict:
    """Extracts claim status details from Waystar response."""
    result = {
        "status": "unknown",
        "status_detail": "",
        "claim_number": "",
        "adjudicated_amount": "",
        "patient_responsibility": "",
        "denial_reason": "",
    }
    claims = response.get("claims", [])
    if not claims:
        return result
    claim = claims[0]
    result["status"] = claim.get("claimStatus", "unknown")
    result["status_detail"] = claim.get("claimStatusDescription", "")
    result["claim_number"] = claim.get("payerClaimNumber", "")
    result["adjudicated_amount"] = claim.get("adjudicatedAmount", "")
    result["patient_responsibility"] = claim.get("patientResponsibilityAmount", "")
    result["denial_reason"] = claim.get("denialReasonDescription", "")
    return result


agent = guava.Agent(
    name="Jordan",
    organization="Riverside Family Medicine Billing",
    purpose=(
        "to help billing staff and patients check the status of submitted claims "
        "through the Waystar RCM platform"
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
            "A caller wants to check the status of an insurance claim. "
            "Collect the necessary details and look up the claim status through Waystar."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling Riverside Family Medicine billing. I'm Jordan. "
                "I can look up claim status for you right now."
            ),
            guava.Field(
                key="patient_last_name",
                field_type="text",
                description="Ask for the patient's last name.",
                required=True,
            ),
            guava.Field(
                key="patient_dob",
                field_type="text",
                description="Ask for the patient's date of birth in YYYY-MM-DD format.",
                required=True,
            ),
            guava.Field(
                key="member_id",
                field_type="text",
                description="Ask for the patient's insurance member ID.",
                required=True,
            ),
            guava.Field(
                key="service_date",
                field_type="text",
                description="Ask for the date of service the claim was submitted for. Capture in YYYY-MM-DD.",
                required=True,
            ),
            guava.Field(
                key="claim_number",
                field_type="text",
                description=(
                    "Ask if they have the payer claim number. It's optional — "
                    "capture it if they have it."
                ),
                required=False,
            ),
        ],
    )


@agent.on_task_complete("look_up_claim")
def on_done(call: guava.Call) -> None:
    last_name = call.get_field("patient_last_name")
    dob = call.get_field("patient_dob")
    member_id = call.get_field("member_id")
    service_date = call.get_field("service_date")
    claim_number = call.get_field("claim_number") or None

    payer_id = os.environ.get("WAYSTAR_PAYER_ID", "00001")
    provider_npi = os.environ["PROVIDER_NPI"]

    logging.info(
        "Waystar claim status lookup — patient: %s, service: %s, claim: %s",
        last_name, service_date, claim_number,
    )

    try:
        response = get_claim_status(
            payer_id=payer_id,
            provider_npi=provider_npi,
            member_id=member_id,
            patient_last_name=last_name,
            patient_dob=dob,
            service_date=service_date,
            claim_number=claim_number,
        )
        status_info = parse_status_response(response)
        logging.info("Waystar claim status: %s", status_info)

        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": "Jordan",
            "use_case": "claim_status_inquiry",
            "patient_last_name": last_name,
            "member_id": member_id,
            "service_date": service_date,
            "claim_status": status_info,
        }
        print(json.dumps(result, indent=2))

        status = status_info.get("status", "unknown")
        status_detail = status_info.get("status_detail", "")
        claim_ref = status_info.get("claim_number", "")
        adj_amount = status_info.get("adjudicated_amount", "")
        patient_resp = status_info.get("patient_responsibility", "")
        denial_reason = status_info.get("denial_reason", "")

        ref_note = f" Payer claim number: {claim_ref}." if claim_ref else ""
        adj_note = f" Adjudicated amount: ${adj_amount}." if adj_amount else ""
        resp_note = f" Patient responsibility: ${patient_resp}." if patient_resp else ""
        denial_note = f" Denial reason: {denial_reason}." if denial_reason else ""

        call.hangup(
            final_instructions=(
                f"Let the caller know the claim status for service date {service_date} is: "
                f"{status} — {status_detail}.{ref_note}{adj_note}{resp_note}{denial_note} "
                "If the claim was denied, let them know the billing team will review and "
                "contact them if any action is required. Thank them for calling."
            )
        )
    except Exception as e:
        logging.error("Waystar claim status lookup failed: %s", e)
        call.hangup(
            final_instructions=(
                "Apologize for a technical issue and let the caller know we were unable "
                "to retrieve the claim status at this time. Ask them to call back or "
                "contact the payer directly. Thank them for their patience."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])

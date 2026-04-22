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


def check_prior_authorization(
    token: str,
    member_id: str,
    date_of_birth: str,
    payer_id: str,
    procedure_code: str = "",
    auth_number: str = "",
) -> dict:
    """
    Look up prior authorization status via the Availity service reviews API.
    Either procedure_code or auth_number can be used to narrow the search.
    """
    params = {
        "memberId": member_id,
        "dateOfBirth": date_of_birth,
        "payerId": payer_id,
        "providerId": AVAILITY_PROVIDER_ID,
    }
    if procedure_code:
        params["procedureCode"] = procedure_code
    if auth_number:
        params["authorizationNumber"] = auth_number

    resp = requests.get(
        f"{BASE_URL}/authorizations",
        headers={"Authorization": f"Bearer {token}"},
        params=params,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def summarize_authorization(auth: dict) -> str:
    auth_number = auth.get("authorizationNumber") or auth.get("id") or "unknown"
    status = auth.get("status") or auth.get("statusDescription") or "unknown"
    service = auth.get("serviceDescription") or auth.get("procedureCode") or ""
    approved_units = auth.get("approvedUnits") or auth.get("quantity") or ""
    effective_date = auth.get("effectiveDate") or auth.get("startDate") or ""
    expiration_date = auth.get("expirationDate") or auth.get("endDate") or ""

    parts = [f"Authorization {auth_number}: status is '{status}'."]
    if service:
        parts.append(f"Service: {service}.")
    if approved_units:
        parts.append(f"Approved units or visits: {approved_units}.")
    if effective_date:
        parts.append(f"Effective: {effective_date}.")
    if expiration_date:
        parts.append(f"Expires: {expiration_date}.")
    return " ".join(parts)


agent = guava.Agent(
    name="Morgan",
    organization="Greenfield Medical Group",
    purpose=(
        "to help patients and clinical staff at Greenfield Medical Group check "
        "whether a prior authorization is in place for a procedure or service"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "prior_authorization_check",
        objective=(
            "A caller needs to verify the status of a prior authorization. Collect "
            "the patient and service details, then look up the authorization through Availity."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling Greenfield Medical Group. This is Morgan. "
                "I can check on a prior authorization for you."
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
                description="Ask for the patient's insurance member ID.",
                required=True,
            ),
            guava.Field(
                key="date_of_birth",
                field_type="text",
                description="Ask for the patient's date of birth in MM/DD/YYYY format.",
                required=True,
            ),
            guava.Field(
                key="payer_name",
                field_type="text",
                description="Ask for the name of the patient's insurance company.",
                required=True,
            ),
            guava.Field(
                key="auth_number",
                field_type="text",
                description=(
                    "Ask if they have a prior authorization number. "
                    "If they don't have it, they can skip this."
                ),
                required=False,
            ),
            guava.Field(
                key="procedure_code",
                field_type="text",
                description=(
                    "Ask for the CPT or procedure code for the service requiring authorization. "
                    "If they don't have the code, ask them to describe the procedure."
                ),
                required=False,
            ),
            guava.Field(
                key="procedure_description",
                field_type="text",
                description=(
                    "If they couldn't provide a procedure code, ask them to describe "
                    "the procedure or service in plain language."
                ),
                required=False,
            ),
        ],
    )


@agent.on_task_complete("prior_authorization_check")
def on_done(call: guava.Call) -> None:
    patient_name = call.get_field("patient_name") or "the patient"
    member_id = (call.get_field("member_id") or "").strip()
    dob = (call.get_field("date_of_birth") or "").strip()
    payer_name = call.get_field("payer_name") or ""
    auth_number = (call.get_field("auth_number") or "").strip()
    procedure_code = (call.get_field("procedure_code") or "").strip()
    procedure_desc = call.get_field("procedure_description") or ""

    payer_id = AVAILITY_PAYER_ID

    logging.info(
        "Checking prior auth for %s — member_id: %s, auth_number: %s, procedure: %s",
        patient_name, member_id, auth_number, procedure_code or procedure_desc,
    )

    try:
        token = get_access_token()
        result = check_prior_authorization(
            token=token,
            member_id=member_id,
            date_of_birth=dob,
            payer_id=payer_id,
            procedure_code=procedure_code,
            auth_number=auth_number,
        )

        authorizations = result.get("authorizations") or result.get("data") or []
        if isinstance(result, dict) and "authorizationNumber" in result:
            authorizations = [result]

        if not authorizations:
            call.hangup(
                final_instructions=(
                    f"Let the caller know no prior authorization was found for {patient_name} "
                    f"with {payer_name} matching the provided details. "
                    "Suggest they contact the payer directly to confirm whether authorization "
                    "is required, or speak with our referrals team about submitting a request. "
                    "Thank them for calling."
                )
            )
            return

        summary = summarize_authorization(authorizations[0])
        logging.info("Prior auth result for %s: %s", patient_name, summary)

        call.hangup(
            final_instructions=(
                f"Share the prior authorization results for {patient_name}: {summary} "
                "If the authorization is approved and current, confirm this clearly and reassuringly. "
                "If it's expired or denied, be empathetic and suggest the caller contact the payer "
                "or speak with our referrals team about resubmitting. "
                "Thank them for calling Greenfield Medical Group."
            )
        )
    except requests.HTTPError as e:
        logging.error("Prior auth lookup failed: %s", e)
        call.hangup(
            final_instructions=(
                "Apologize — the system returned an error when checking the authorization. "
                "Suggest the caller verify directly through the Availity portal or by calling "
                "the payer's provider services line. Thank them for their patience."
            )
        )
    except Exception as e:
        logging.error("Unexpected error in prior auth check: %s", e)
        call.hangup(
            final_instructions=(
                "Apologize for a technical issue. Let the caller know our team will "
                "follow up with the authorization status. Thank them for calling."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])

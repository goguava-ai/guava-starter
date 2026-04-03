import guava
import os
import logging
import json
import requests
from datetime import datetime

logging.basicConfig(level=logging.INFO)

CLIENT_ID = os.environ["CHANGE_HEALTHCARE_CLIENT_ID"]
CLIENT_SECRET = os.environ["CHANGE_HEALTHCARE_CLIENT_SECRET"]
BASE_URL = os.environ.get("CHANGE_HEALTHCARE_BASE_URL", "https://apis.changehealthcare.com")


def get_access_token() -> str:
    resp = requests.post(
        f"{BASE_URL}/apip/auth/v2/token",
        json={"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def get_claim_status(
    payer_id: str,
    provider_npi: str,
    patient_member_id: str,
    patient_last_name: str,
    patient_date_of_birth: str,
    service_date: str,
) -> dict:
    """Submits a 276 claim status inquiry and returns the 277 response."""
    token = get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    control_number = datetime.utcnow().strftime("%H%M%S%f")[:9]
    payload = {
        "controlNumber": control_number,
        "tradingPartnerServiceId": payer_id,
        "providers": [
            {
                "providerType": "BillingProvider",
                "npi": provider_npi,
                "organizationName": "Valley Medical Group",
            }
        ],
        "subscriber": {
            "memberId": patient_member_id,
            "lastName": patient_last_name,
            "dateOfBirth": patient_date_of_birth,
        },
        "claimInformation": {
            "patientControlNumber": "",
            "claimAmount": "",
            "serviceStartDate": service_date,
        },
    }
    resp = requests.post(
        f"{BASE_URL}/medicalnetwork/claimstatus/v3",
        headers=headers,
        json=payload,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def parse_claim_status(response: dict) -> dict:
    """Extracts the status code and human-readable description from a 277 response."""
    result = {"status": "unknown", "status_description": "", "claim_reference": ""}
    claims = response.get("claimStatuses", [])
    if not claims:
        return result
    claim = claims[0]
    statuses = claim.get("claimStatusDetails", [])
    if statuses:
        detail = statuses[0]
        status_code = detail.get("statusCode", "")
        result["status_code"] = status_code
        # Common X12 277 status codes
        code_map = {
            "F0": "Finalized/Payment",
            "F1": "Finalized/Denial",
            "F2": "Finalized/Revised",
            "P1": "Pending/In Process",
            "P2": "Pending/Payer Review",
            "R0": "Returned to Provider",
            "R3": "Returned — Incorrect Claim",
            "D0": "Data Reporting Only",
        }
        result["status_description"] = code_map.get(status_code, detail.get("statusDescription", ""))
        result["claim_reference"] = claim.get("claimControlNumber", "")
        result["payer_claim_number"] = detail.get("payerClaimControlNumber", "")
        result["adjudication_date"] = detail.get("claimStatusEffectiveDate", "")
    return result


class ClaimStatusController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Valley Medical Group Billing",
            agent_name="Dana",
            agent_purpose=(
                "to help patients and provider staff check the status of a submitted "
                "insurance claim"
            ),
        )

        self.set_task(
            objective=(
                "A caller is checking on the status of a submitted claim. Collect the "
                "information needed to look up the claim and report back the current status."
            ),
            checklist=[
                guava.Say(
                    "Thank you for calling Valley Medical Group billing. I'm Dana. "
                    "I can look up the status of a claim for you right now."
                ),
                guava.Field(
                    key="patient_last_name",
                    field_type="text",
                    description="Ask for the patient's last name.",
                    required=True,
                ),
                guava.Field(
                    key="patient_date_of_birth",
                    field_type="text",
                    description="Ask for the patient's date of birth. Capture in YYYY-MM-DD format.",
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
                    description=(
                        "Ask for the approximate date of service for the claim. "
                        "Capture in YYYY-MM-DD format."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="payer_name",
                    field_type="text",
                    description="Ask which insurance company the claim was submitted to.",
                    required=True,
                ),
            ],
            on_complete=self.look_up_claim,
        )

        self.accept_call()

    def look_up_claim(self):
        last_name = self.get_field("patient_last_name")
        dob = self.get_field("patient_date_of_birth")
        member_id = self.get_field("member_id")
        service_date = self.get_field("service_date")
        payer_name = self.get_field("payer_name")

        # In production, map payer_name to the correct payer ID from your payer directory
        payer_id = os.environ.get("CHANGE_HEALTHCARE_TRADING_PARTNER_ID", "000050")
        provider_npi = os.environ["PROVIDER_NPI"]

        logging.info(
            "Checking claim status for %s (DOB: %s, member: %s, service: %s)",
            last_name, dob, member_id, service_date,
        )

        try:
            response = get_claim_status(
                payer_id=payer_id,
                provider_npi=provider_npi,
                patient_member_id=member_id,
                patient_last_name=last_name,
                patient_date_of_birth=dob,
                service_date=service_date,
            )
            claim_info = parse_claim_status(response)
            logging.info("Claim status result: %s", claim_info)

            result = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "agent": "Dana",
                "use_case": "claim_status",
                "patient_last_name": last_name,
                "member_id": member_id,
                "service_date": service_date,
                "payer": payer_name,
                "claim_status": claim_info,
            }
            print(json.dumps(result, indent=2))

            status_desc = claim_info.get("status_description") or claim_info.get("status", "unknown")
            claim_ref = claim_info.get("payer_claim_number") or claim_info.get("claim_reference", "")
            adj_date = claim_info.get("adjudication_date", "")

            ref_note = f" The payer claim reference number is {claim_ref}." if claim_ref else ""
            date_note = f" The adjudication date on file is {adj_date}." if adj_date else ""

            self.hangup(
                final_instructions=(
                    f"Let the caller know that the claim status for the service date of "
                    f"{service_date} is: {status_desc}.{ref_note}{date_note} "
                    "If the status is a denial or returned claim, let them know that our "
                    "billing team will review it and contact them if any action is needed. "
                    "Thank them for calling Valley Medical Group billing."
                )
            )
        except Exception as e:
            logging.error("Claim status lookup failed: %s", e)
            self.hangup(
                final_instructions=(
                    "Apologize for a technical issue and let the caller know we were unable to "
                    "retrieve the claim status at this time. Advise them to call back or contact "
                    "their insurance company directly for an update. Thank them for their patience."
                )
            )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=ClaimStatusController,
    )

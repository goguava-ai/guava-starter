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


def check_prior_auth(
    payer_id: str,
    provider_npi: str,
    member_id: str,
    first_name: str,
    last_name: str,
    date_of_birth: str,
    procedure_code: str,
    service_date: str,
) -> dict:
    """Submits a 278 prior authorization inquiry to the payer."""
    token = get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    control_number = datetime.utcnow().strftime("%H%M%S%f")[:9]
    payload = {
        "controlNumber": control_number,
        "tradingPartnerServiceId": payer_id,
        "requestType": "HealthCareServicesReviewInformation",
        "provider": {
            "npi": provider_npi,
            "organizationName": "Valley Medical Group",
        },
        "subscriber": {
            "memberId": member_id,
            "firstName": first_name,
            "lastName": last_name,
            "dateOfBirth": date_of_birth,
        },
        "serviceReview": {
            "serviceType": "MedicalCare",
            "serviceDate": service_date,
            "procedureCode": procedure_code,
            "quantity": "1",
            "quantityType": "Units",
        },
    }
    resp = requests.post(
        f"{BASE_URL}/medicalnetwork/priorauthorization/v3",
        headers=headers,
        json=payload,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def parse_auth_response(response: dict) -> dict:
    """Extracts authorization status and key details from a 278 response."""
    result = {
        "status": "unknown",
        "auth_number": "",
        "effective_date": "",
        "expiration_date": "",
        "notes": "",
    }
    services = response.get("serviceReviewInformation", [])
    if not services:
        return result
    service = services[0]
    # X12 278 review action codes
    action_map = {
        "A1": "Certified — approved",
        "A2": "Not Certified — denied",
        "A3": "Modified — partial approval",
        "A4": "Additional Information Required",
        "A6": "Modified — services certified",
    }
    action_code = service.get("actionCode", "")
    result["status"] = action_map.get(action_code, f"Action code: {action_code}")
    result["auth_number"] = service.get("authorizationNumber", "")
    result["effective_date"] = service.get("certificationEffectiveDate", "")
    result["expiration_date"] = service.get("certificationExpirationDate", "")
    result["notes"] = service.get("additionalMessage", "")
    return result


class PriorAuthStatusController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Valley Medical Group",
            agent_name="Morgan",
            agent_purpose=(
                "to help patients and clinical staff check whether a prior authorization "
                "has been approved for a procedure or service"
            ),
        )

        self.set_task(
            objective=(
                "A caller wants to know the prior authorization status for a scheduled "
                "procedure. Collect the necessary information and look up the auth status."
            ),
            checklist=[
                guava.Say(
                    "Thank you for calling Valley Medical Group. I'm Morgan. "
                    "I can check prior authorization status for you."
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
                    key="procedure_description",
                    field_type="text",
                    description=(
                        "Ask what procedure or service they need authorization for. "
                        "Capture the procedure name or description as they describe it."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="procedure_code",
                    field_type="text",
                    description=(
                        "Ask if they have the CPT or procedure code. It's optional — "
                        "capture it if they have it, otherwise skip."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="service_date",
                    field_type="text",
                    description=(
                        "Ask for the planned date of service. Capture in YYYY-MM-DD format."
                    ),
                    required=True,
                ),
            ],
            on_complete=self.check_auth_status,
        )

        self.accept_call()

    def check_auth_status(self):
        first_name = self.get_field("first_name")
        last_name = self.get_field("last_name")
        dob = self.get_field("date_of_birth")
        member_id = self.get_field("member_id")
        procedure_desc = self.get_field("procedure_description")
        procedure_code = self.get_field("procedure_code") or "99213"  # default to E&M if not given
        service_date = self.get_field("service_date")

        payer_id = os.environ.get("CHANGE_HEALTHCARE_TRADING_PARTNER_ID", "000050")
        provider_npi = os.environ["PROVIDER_NPI"]

        logging.info(
            "Checking prior auth for %s %s — procedure: %s (%s), service date: %s",
            first_name, last_name, procedure_desc, procedure_code, service_date,
        )

        try:
            response = check_prior_auth(
                payer_id=payer_id,
                provider_npi=provider_npi,
                member_id=member_id,
                first_name=first_name,
                last_name=last_name,
                date_of_birth=dob,
                procedure_code=procedure_code,
                service_date=service_date,
            )
            auth_info = parse_auth_response(response)
            logging.info("Prior auth result for %s: %s", member_id, auth_info)

            result = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "agent": "Morgan",
                "use_case": "prior_auth_status",
                "patient": {"first_name": first_name, "last_name": last_name},
                "member_id": member_id,
                "procedure": procedure_desc,
                "service_date": service_date,
                "auth": auth_info,
            }
            print(json.dumps(result, indent=2))

            status = auth_info.get("status", "unknown")
            auth_num = auth_info.get("auth_number", "")
            exp_date = auth_info.get("expiration_date", "")
            notes = auth_info.get("notes", "")

            auth_ref = f" The authorization number is {auth_num}." if auth_num else ""
            exp_note = f" This authorization is valid through {exp_date}." if exp_date else ""
            extra = f" Note: {notes}" if notes else ""

            self.hangup(
                final_instructions=(
                    f"Let {first_name} know that the prior authorization status for "
                    f"'{procedure_desc}' scheduled on {service_date} is: {status}.{auth_ref}{exp_note}{extra} "
                    "If the authorization is approved, remind them to bring their insurance card "
                    "to their appointment. If additional information is required, let them know "
                    "that a member of our clinical team will be in touch. "
                    "Thank them for calling Valley Medical Group."
                )
            )
        except Exception as e:
            logging.error("Prior auth check failed: %s", e)
            self.hangup(
                final_instructions=(
                    f"Apologize to {first_name} for a technical issue and let them know we "
                    "were unable to retrieve the authorization status at this time. "
                    "Let them know our billing team will follow up by phone or ask them to "
                    "call back. Thank them for their patience."
                )
            )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=PriorAuthStatusController,
    )

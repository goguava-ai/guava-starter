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


def lookup_prior_auth(
    payer_id: str,
    provider_npi: str,
    member_id: str,
    first_name: str,
    last_name: str,
    date_of_birth: str,
    procedure_code: str,
    service_date: str,
) -> dict:
    """Submits a prior authorization inquiry to Waystar."""
    token = get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "payerId": payer_id,
        "requestType": "inquiry",
        "provider": {
            "npi": provider_npi,
            "organizationName": "Riverside Family Medicine",
        },
        "subscriber": {
            "memberId": member_id,
            "firstName": first_name,
            "lastName": last_name,
            "dateOfBirth": date_of_birth,
        },
        "services": [
            {
                "procedureCode": procedure_code,
                "serviceDate": service_date,
                "quantity": 1,
                "quantityType": "units",
            }
        ],
    }
    resp = requests.post(
        f"{WAYSTAR_BASE_URL}/priorauth/v1/inquiries",
        headers=headers,
        json=payload,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def parse_auth_result(response: dict) -> dict:
    """Extracts authorization details from the Waystar prior auth response."""
    result = {
        "decision": "unknown",
        "auth_number": "",
        "effective_date": "",
        "expiration_date": "",
        "approved_units": "",
        "notes": "",
    }
    auths = response.get("authorizations", [])
    if not auths:
        return result
    auth = auths[0]
    result["decision"] = auth.get("decision", "unknown")
    result["auth_number"] = auth.get("authorizationNumber", "")
    result["effective_date"] = auth.get("effectiveDate", "")
    result["expiration_date"] = auth.get("expirationDate", "")
    result["approved_units"] = str(auth.get("approvedQuantity", ""))
    result["notes"] = auth.get("notes", "")
    return result


class PriorAuthLookupController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Riverside Family Medicine",
            agent_name="Casey",
            agent_purpose=(
                "to help clinical and administrative staff check prior authorization status "
                "for scheduled procedures through Waystar"
            ),
        )

        self.set_task(
            objective=(
                "A caller needs to check whether a prior authorization has been obtained "
                "for a patient's procedure. Collect the necessary details and look it up."
            ),
            checklist=[
                guava.Say(
                    "Thank you for calling Riverside Family Medicine. I'm Casey. "
                    "I can look up prior authorization status for a procedure."
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
                    description="Ask what procedure or service requires authorization.",
                    required=True,
                ),
                guava.Field(
                    key="procedure_code",
                    field_type="text",
                    description="Ask for the CPT or procedure code if they have it. Optional.",
                    required=False,
                ),
                guava.Field(
                    key="service_date",
                    field_type="text",
                    description="Ask for the planned date of service in YYYY-MM-DD format.",
                    required=True,
                ),
            ],
            on_complete=self.check_auth,
        )

        self.accept_call()

    def check_auth(self):
        first_name = self.get_field("first_name")
        last_name = self.get_field("last_name")
        dob = self.get_field("date_of_birth")
        member_id = self.get_field("member_id")
        procedure_desc = self.get_field("procedure_description")
        procedure_code = self.get_field("procedure_code") or "99213"
        service_date = self.get_field("service_date")

        payer_id = os.environ.get("WAYSTAR_PAYER_ID", "00001")
        provider_npi = os.environ["PROVIDER_NPI"]

        logging.info(
            "Waystar prior auth lookup for %s %s — procedure: %s, date: %s",
            first_name, last_name, procedure_desc, service_date,
        )

        try:
            response = lookup_prior_auth(
                payer_id=payer_id,
                provider_npi=provider_npi,
                member_id=member_id,
                first_name=first_name,
                last_name=last_name,
                date_of_birth=dob,
                procedure_code=procedure_code,
                service_date=service_date,
            )
            auth_info = parse_auth_result(response)
            logging.info("Prior auth result: %s", auth_info)

            result = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "agent": "Casey",
                "use_case": "prior_auth_lookup",
                "patient": {"first_name": first_name, "last_name": last_name},
                "member_id": member_id,
                "procedure": procedure_desc,
                "procedure_code": procedure_code,
                "service_date": service_date,
                "auth": auth_info,
            }
            print(json.dumps(result, indent=2))

            decision = auth_info.get("decision", "unknown").lower()
            auth_num = auth_info.get("auth_number", "")
            exp_date = auth_info.get("expiration_date", "")
            units = auth_info.get("approved_units", "")
            notes = auth_info.get("notes", "")

            auth_ref = f" Authorization number: {auth_num}." if auth_num else ""
            exp_note = f" Valid through {exp_date}." if exp_date else ""
            units_note = f" Approved units: {units}." if units else ""
            extra = f" Note: {notes}" if notes else ""

            if "approved" in decision or "certified" in decision:
                self.hangup(
                    final_instructions=(
                        f"Let the caller know that the prior authorization for '{procedure_desc}' "
                        f"for {first_name} {last_name} on {service_date} has been approved.{auth_ref}{exp_note}{units_note}{extra} "
                        "Remind them to reference the authorization number when scheduling. "
                        "Thank them for calling Riverside Family Medicine."
                    )
                )
            elif "denied" in decision or "not certified" in decision:
                self.hangup(
                    final_instructions=(
                        f"Let the caller know that the prior authorization for '{procedure_desc}' "
                        f"was not approved.{extra} "
                        "Let them know our clinical team will review the denial and may pursue "
                        "an appeal. Ask them to contact our prior auth team for next steps. "
                        "Thank them for calling."
                    )
                )
            elif "pending" in decision or "additional" in decision:
                self.hangup(
                    final_instructions=(
                        f"Let the caller know the authorization request for '{procedure_desc}' "
                        f"is still pending or requires additional information.{extra} "
                        "Let them know our prior authorization team will follow up with the "
                        "payer and contact them with an update. Thank them for calling."
                    )
                )
            else:
                self.hangup(
                    final_instructions=(
                        f"Let the caller know we retrieved authorization information for "
                        f"'{procedure_desc}' but the decision status is: {decision}.{auth_ref}{extra} "
                        "Recommend they contact our prior auth team for clarification. "
                        "Thank them for calling."
                    )
                )
        except Exception as e:
            logging.error("Waystar prior auth lookup failed: %s", e)
            self.hangup(
                final_instructions=(
                    f"Apologize to the caller for a technical issue and let them know we "
                    "were unable to retrieve the authorization status. Ask them to try again "
                    "or contact the payer directly. Thank them for their patience."
                )
            )


if __name__ == "__main__":
    logging_utils.configure_logging()
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=PriorAuthLookupController,
    )

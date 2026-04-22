import guava
import os
import logging
from guava import logging_utils
import json
import requests
from datetime import datetime, timezone


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


def check_eligibility(
    trading_partner_id: str,
    member_id: str,
    first_name: str,
    last_name: str,
    date_of_birth: str,
    provider_npi: str,
    service_type_code: str = "30",
) -> dict:
    """Submits a 270 real-time eligibility inquiry and returns the 271 response."""
    token = get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    control_number = datetime.now(timezone.utc).strftime("%H%M%S%f")[:9]
    payload = {
        "controlNumber": control_number,
        "tradingPartnerServiceId": trading_partner_id,
        "provider": {
            "organizationName": "Valley Medical Group",
            "npi": provider_npi,
        },
        "subscriber": {
            "memberId": member_id,
            "firstName": first_name,
            "lastName": last_name,
            "dateOfBirth": date_of_birth,
        },
        "encounter": {
            "serviceTypeCodes": [service_type_code],
            "dateOfService": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        },
    }
    resp = requests.post(
        f"{BASE_URL}/medicalnetwork/eligibility/v3",
        headers=headers,
        json=payload,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def summarize_eligibility(response: dict) -> dict:
    """Pulls the key coverage fields out of the 271 response for the agent to read."""
    plan = {}
    benefits = response.get("benefitsInformation", [])
    for b in benefits:
        code = b.get("code", "")
        if code == "1":  # Active Coverage
            plan["status"] = "active"
            plan["plan_name"] = b.get("planDescription", "")
            plan["group_number"] = b.get("groupOrPolicyNumber", "")
        elif code == "C":  # Copayment
            plan["copay"] = b.get("benefitAmount", "")
        elif code == "G":  # Deductible
            plan["deductible"] = b.get("benefitAmount", "")
            plan["deductible_remaining"] = b.get("benefitAmountRemainingForCalendarYear", "")
    if not plan:
        plan["status"] = "could not determine"
    return plan


class EligibilityCheckController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Valley Medical Group",
            agent_name="Alex",
            agent_purpose=(
                "to help patients verify their insurance eligibility before their appointment "
                "so they know what to expect at check-in"
            ),
        )

        self.set_task(
            objective=(
                "A patient is calling to verify their insurance coverage before an upcoming "
                "appointment. Greet them and collect their insurance and identity information "
                "so we can perform a real-time eligibility check."
            ),
            checklist=[
                guava.Say(
                    "Thank you for calling Valley Medical Group. I'm Alex, and I can help you "
                    "verify your insurance coverage before your appointment. "
                    "This will only take a moment."
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
                    description=(
                        "Ask for the patient's date of birth. Capture in YYYY-MM-DD format."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="member_id",
                    field_type="text",
                    description=(
                        "Ask for their insurance member ID, which is printed on their insurance card."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="insurance_name",
                    field_type="text",
                    description="Ask which insurance plan they have (e.g. Blue Cross, Aetna, United).",
                    required=True,
                ),
            ],
            on_complete=self.run_eligibility_check,
        )

        self.accept_call()

    def run_eligibility_check(self):
        first_name = self.get_field("first_name")
        last_name = self.get_field("last_name")
        dob = self.get_field("date_of_birth")
        member_id = self.get_field("member_id")
        insurance_name = self.get_field("insurance_name")

        logging.info(
            "Running eligibility check for %s %s (DOB: %s, member: %s)",
            first_name, last_name, dob, member_id,
        )

        # The trading partner ID maps to the specific payer. In production this would be
        # looked up from a payer directory based on the insurance name the caller provided.
        trading_partner_id = os.environ.get("CHANGE_HEALTHCARE_TRADING_PARTNER_ID", "000050")
        provider_npi = os.environ["PROVIDER_NPI"]

        try:
            response = check_eligibility(
                trading_partner_id=trading_partner_id,
                member_id=member_id,
                first_name=first_name,
                last_name=last_name,
                date_of_birth=dob,
                provider_npi=provider_npi,
            )
            coverage = summarize_eligibility(response)
            logging.info("Eligibility result for %s: %s", member_id, coverage)

            result = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "agent": "Alex",
                "use_case": "eligibility_check",
                "patient": {"first_name": first_name, "last_name": last_name, "dob": dob},
                "member_id": member_id,
                "insurance": insurance_name,
                "coverage": coverage,
            }
            print(json.dumps(result, indent=2))

            status = coverage.get("status", "could not determine")
            plan_name = coverage.get("plan_name", insurance_name)
            copay = coverage.get("copay", "")
            deductible = coverage.get("deductible", "")
            deductible_remaining = coverage.get("deductible_remaining", "")

            if status == "active":
                benefit_details = f"Your {plan_name} coverage is currently active."
                if copay:
                    benefit_details += f" Your expected copay for this visit is ${copay}."
                if deductible and deductible_remaining:
                    benefit_details += (
                        f" Your deductible is ${deductible}, "
                        f"with ${deductible_remaining} remaining for this year."
                    )
                self.hangup(
                    final_instructions=(
                        f"Let {first_name} know the following: {benefit_details} "
                        "Remind them to bring their insurance card and a valid photo ID to their "
                        "appointment, and to arrive 10 minutes early to complete any paperwork. "
                        "Thank them for calling Valley Medical Group."
                    )
                )
            else:
                self.hangup(
                    final_instructions=(
                        f"Let {first_name} know that we were unable to confirm active coverage "
                        f"for their {insurance_name} plan with the member ID they provided. "
                        "Ask them to double-check the information on their insurance card and "
                        "call back, or suggest they contact their insurance company directly. "
                        "Let them know our billing team is also available to help. "
                        "Thank them for calling."
                    )
                )
        except Exception as e:
            logging.error("Eligibility check failed: %s", e)
            self.hangup(
                final_instructions=(
                    f"Apologize to {first_name} for a technical issue and let them know we were "
                    "unable to complete the eligibility check at this time. Ask them to call back "
                    "in a few minutes or contact their insurance company directly to verify "
                    "coverage. Thank them for their patience."
                )
            )


if __name__ == "__main__":
    logging_utils.configure_logging()
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=EligibilityCheckController,
    )

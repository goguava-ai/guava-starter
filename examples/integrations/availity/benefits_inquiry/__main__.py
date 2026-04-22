import guava
import os
import logging
from guava import logging_utils
import requests


AVAILITY_CLIENT_ID = os.environ["AVAILITY_CLIENT_ID"]
AVAILITY_CLIENT_SECRET = os.environ["AVAILITY_CLIENT_SECRET"]
AVAILITY_PROVIDER_ID = os.environ["AVAILITY_PROVIDER_ID"]
AVAILITY_PAYER_ID = os.environ.get("AVAILITY_PAYER_ID", "")

BASE_URL = "https://api.availity.com/availity/v1"
TOKEN_URL = f"{BASE_URL}/token"

# Availity service type codes for common benefit categories.
SERVICE_TYPE_CODES = {
    "primary care visit": "98",
    "specialist visit": "96",
    "emergency room": "86",
    "inpatient hospital": "12",
    "outpatient hospital": "13",
    "mental health": "MH",
    "prescription drugs": "88",
    "preventive care": "98",
    "lab work": "5",
    "imaging or radiology": "62",
    "physical therapy": "PT",
    "general coverage": "30",
}


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


def get_benefits(
    token: str,
    member_id: str,
    date_of_birth: str,
    payer_id: str,
    service_type_code: str = "30",
) -> dict:
    """Retrieve benefit details for a specific service type via Availity coverages."""
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


def extract_benefit_summary(coverage: dict, service_type: str) -> str:
    """Parse the coverage response into a spoken benefits summary."""
    parts = []

    # Coverage status
    status = coverage.get("subscriberStatus") or coverage.get("status") or "active"
    parts.append(f"Coverage status: {status}.")

    # Plan info
    plan = coverage.get("planDescription") or coverage.get("groupDescription") or ""
    if plan:
        parts.append(f"Plan: {plan}.")

    # Deductible
    benefits = coverage.get("benefits") or []
    for benefit in benefits:
        benefit_type = (benefit.get("benefitDescription") or "").lower()
        amount = benefit.get("benefitAmount") or ""
        remaining = benefit.get("benefitAmountRemaining") or ""
        period = benefit.get("timePeriodQualifier") or "calendar year"

        if "deductible" in benefit_type and amount:
            remaining_note = f" ({remaining} remaining)" if remaining else ""
            parts.append(f"Deductible: ${amount}{remaining_note} per {period}.")
        elif "out-of-pocket" in benefit_type and amount:
            remaining_note = f" ({remaining} remaining)" if remaining else ""
            parts.append(f"Out-of-pocket maximum: ${amount}{remaining_note} per {period}.")
        elif "copay" in benefit_type and amount:
            parts.append(f"Copay for {service_type}: ${amount}.")
        elif "coinsurance" in benefit_type and amount:
            parts.append(f"Coinsurance for {service_type}: {amount}%.")

    if not benefits:
        parts.append(
            "Detailed benefit amounts were not returned. "
            "The patient should verify copays and deductibles directly with their insurer."
        )

    return " ".join(parts)


class BenefitsInquiryController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Greenfield Medical Group",
            agent_name="Alex",
            agent_purpose=(
                "to help patients understand their insurance benefits — including deductibles, "
                "copays, and out-of-pocket costs — for upcoming visits to Greenfield Medical Group"
            ),
        )

        self.set_task(
            objective=(
                "A patient is calling to understand their insurance benefits before an upcoming "
                "visit. Collect their information and service type, check their benefits through "
                "Availity, and share the results in plain language."
            ),
            checklist=[
                guava.Say(
                    "Thank you for calling Greenfield Medical Group. This is Alex. "
                    "I can help you understand your insurance benefits for your upcoming visit. "
                    "Please have your insurance card ready."
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
                    description="Ask for their member ID as it appears on their insurance card.",
                    required=True,
                ),
                guava.Field(
                    key="date_of_birth",
                    field_type="text",
                    description="Ask for their date of birth in MM/DD/YYYY format.",
                    required=True,
                ),
                guava.Field(
                    key="payer_name",
                    field_type="text",
                    description="Ask for the name of their insurance company.",
                    required=True,
                ),
                guava.Field(
                    key="service_type",
                    field_type="multiple_choice",
                    description=(
                        "Ask what type of visit or service they're scheduling, so we can "
                        "look up the right benefit information."
                    ),
                    choices=list(SERVICE_TYPE_CODES.keys()),
                    required=True,
                ),
            ],
            on_complete=self.retrieve_benefits,
        )

        self.accept_call()

    def retrieve_benefits(self):
        patient_name = self.get_field("patient_name") or "the patient"
        member_id = (self.get_field("member_id") or "").strip()
        dob = (self.get_field("date_of_birth") or "").strip()
        payer_name = self.get_field("payer_name") or ""
        service_type = self.get_field("service_type") or "general coverage"
        service_code = SERVICE_TYPE_CODES.get(service_type, "30")

        payer_id = AVAILITY_PAYER_ID

        logging.info(
            "Retrieving benefits for %s — member_id: %s, service: %s (code: %s)",
            patient_name, member_id, service_type, service_code,
        )

        try:
            token = get_access_token()
            coverage = get_benefits(
                token=token,
                member_id=member_id,
                date_of_birth=dob,
                payer_id=payer_id,
                service_type_code=service_code,
            )
            summary = extract_benefit_summary(coverage, service_type)
            logging.info("Benefits result for %s: %s", patient_name, summary)

            self.hangup(
                final_instructions=(
                    f"Share the following benefit information with {patient_name} in a clear, "
                    f"friendly way: {summary} "
                    "Translate any jargon into plain language — for example, explain what "
                    "'deductible' and 'coinsurance' mean if needed. "
                    "Remind them that these are estimates and actual costs may vary depending "
                    "on the specific services rendered. Encourage them to call their insurer "
                    "for a formal benefits summary if they need one in writing. "
                    "Thank them for calling Greenfield Medical Group."
                )
            )
        except requests.HTTPError as e:
            status_code = e.response.status_code if e.response else 0
            if status_code == 404:
                logging.warning("No benefits found for member_id %s", member_id)
                self.hangup(
                    final_instructions=(
                        f"Let {patient_name} know that their insurance information couldn't be "
                        f"located with the provided details. Suggest they call their insurer "
                        "directly using the number on the back of their insurance card for benefit details. "
                        "Thank them for calling."
                    )
                )
            else:
                logging.error("Benefits inquiry failed (%s): %s", status_code, e)
                self.hangup(
                    final_instructions=(
                        "Apologize for a technical issue. Let the patient know they can call their "
                        "insurer directly for benefit details, or our billing team can assist them "
                        "before their appointment. Thank them for their patience."
                    )
                )
        except Exception as e:
            logging.error("Benefits inquiry error: %s", e)
            self.hangup(
                final_instructions=(
                    "Apologize for a technical difficulty. Let the patient know our billing team "
                    "can review their benefits with them before or at their appointment. "
                    "Thank them for calling Greenfield Medical Group."
                )
            )


if __name__ == "__main__":
    logging_utils.configure_logging()
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=BenefitsInquiryController,
    )

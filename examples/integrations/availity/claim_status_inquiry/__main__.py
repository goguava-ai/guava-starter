import guava
import os
import logging
import requests

logging.basicConfig(level=logging.INFO)

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


def get_claim_status(
    token: str,
    member_id: str,
    date_of_birth: str,
    payer_id: str,
    claim_id: str = "",
    date_of_service: str = "",
) -> dict:
    """
    Submit a claim status inquiry (276/277) to Availity.
    Either claim_id or date_of_service should be provided.
    """
    params = {
        "memberId": member_id,
        "dateOfBirth": date_of_birth,
        "payerId": payer_id,
        "providerId": AVAILITY_PROVIDER_ID,
    }
    if claim_id:
        params["claimId"] = claim_id
    if date_of_service:
        params["serviceStartDate"] = date_of_service

    resp = requests.get(
        f"{BASE_URL}/claim-statuses",
        headers={"Authorization": f"Bearer {token}"},
        params=params,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def summarize_claim(claim: dict) -> str:
    """Return a human-readable claim status summary."""
    claim_id = claim.get("claimId") or claim.get("id") or "unknown"
    status = claim.get("status") or claim.get("statusDescription") or "unknown"
    service_date = claim.get("serviceDate") or claim.get("dateOfService") or ""
    amount_billed = claim.get("amountBilled") or ""
    amount_paid = claim.get("amountPaid") or ""
    denial_reason = claim.get("denialReason") or claim.get("adjustmentReason") or ""

    parts = [f"Claim {claim_id}: status is '{status}'."]
    if service_date:
        parts.append(f"Date of service: {service_date}.")
    if amount_billed:
        parts.append(f"Amount billed: ${amount_billed}.")
    if amount_paid:
        parts.append(f"Amount paid by insurance: ${amount_paid}.")
    if denial_reason:
        parts.append(f"Adjustment or denial reason: {denial_reason}.")
    return " ".join(parts)


class ClaimStatusInquiryController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Greenfield Medical Group",
            agent_name="Casey",
            agent_purpose=(
                "to help patients and billing staff at Greenfield Medical Group check "
                "the status of insurance claims"
            ),
        )

        self.set_task(
            objective=(
                "A caller needs to check on a claim. Collect identifying information and "
                "look up the claim status through Availity."
            ),
            checklist=[
                guava.Say(
                    "Thank you for calling Greenfield Medical Group billing. This is Casey. "
                    "I can look up a claim status for you."
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
                    key="lookup_method",
                    field_type="multiple_choice",
                    description=(
                        "Ask whether they have a specific claim ID, or if they'd like to "
                        "search by date of service."
                    ),
                    choices=["claim ID", "date of service"],
                    required=True,
                ),
                guava.Field(
                    key="lookup_value",
                    field_type="text",
                    description=(
                        "Ask for the claim ID or date of service (MM/DD/YYYY), depending on "
                        "their choice."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="payer_name",
                    field_type="text",
                    description="Ask for the name of the insurance company.",
                    required=True,
                ),
            ],
            on_complete=self.look_up_claim,
        )

        self.accept_call()

    def look_up_claim(self):
        patient_name = self.get_field("patient_name") or "the patient"
        member_id = (self.get_field("member_id") or "").strip()
        dob = (self.get_field("date_of_birth") or "").strip()
        method = self.get_field("lookup_method") or "claim ID"
        lookup_value = (self.get_field("lookup_value") or "").strip()
        payer_name = self.get_field("payer_name") or ""

        payer_id = AVAILITY_PAYER_ID
        claim_id = lookup_value if method == "claim ID" else ""
        date_of_service = lookup_value if method == "date of service" else ""

        logging.info(
            "Checking claim status for %s — member_id: %s, method: %s, value: %s",
            patient_name, member_id, method, lookup_value,
        )

        try:
            token = get_access_token()
            result = get_claim_status(
                token=token,
                member_id=member_id,
                date_of_birth=dob,
                payer_id=payer_id,
                claim_id=claim_id,
                date_of_service=date_of_service,
            )

            claims = result.get("claims") or result.get("data") or []
            if isinstance(result, dict) and "claimId" in result:
                claims = [result]

            if not claims:
                self.hangup(
                    final_instructions=(
                        f"Let the caller know no claims were found for {patient_name} "
                        f"matching the provided information. Suggest they verify the claim ID "
                        "or date of service, or contact the insurer directly. "
                        "Thank them for calling."
                    )
                )
                return

            summary = summarize_claim(claims[0])
            logging.info("Claim status for %s: %s", patient_name, summary)

            self.hangup(
                final_instructions=(
                    f"Share the claim status with the caller for {patient_name}: {summary} "
                    "If the claim was denied, be empathetic and explain that they can request "
                    "an explanation of benefits from their insurer or speak with our billing team "
                    "about next steps. If it's paid, confirm the amounts clearly. "
                    "Thank them for calling Greenfield Medical Group."
                )
            )
        except requests.HTTPError as e:
            logging.error("Claim status lookup failed: %s", e)
            self.hangup(
                final_instructions=(
                    "Apologize — there was an issue retrieving the claim status. "
                    "Let the caller know they can also check the Availity portal directly "
                    "or call the payer's provider line. Thank them for their patience."
                )
            )
        except Exception as e:
            logging.error("Unexpected error in claim status lookup: %s", e)
            self.hangup(
                final_instructions=(
                    "Apologize for a technical issue. Let the caller know our billing team "
                    "will follow up with the claim status by the end of the business day. "
                    "Thank them for their patience."
                )
            )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=ClaimStatusInquiryController,
    )

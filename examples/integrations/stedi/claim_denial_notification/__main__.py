import guava
import os
import logging
import argparse
import random
import requests

logging.basicConfig(level=logging.INFO)

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


class ClaimDenialNotificationController(guava.CallController):
    def __init__(
        self,
        patient_name: str,
        first_name: str,
        last_name: str,
        date_of_birth: str,
        member_id: str,
        payer_id: str,
        claim_number: str,
        service_description: str,
    ):
        super().__init__()
        self.patient_name = patient_name
        self.claim_number = claim_number
        self.service_description = service_description
        self.denial_description = ""
        self.is_denied = False

        # Check the claim status before calling so we only place the call if it's actually denied.
        try:
            result = check_claim_status(
                payer_id, member_id, first_name, last_name, date_of_birth, claim_number
            )
            self.is_denied, _, self.denial_description = get_denial_details(result)
            logging.info(
                "Pre-call claim check for #%s — denied: %s, reason: %s",
                claim_number, self.is_denied, self.denial_description,
            )
        except Exception as e:
            logging.error("Pre-call claim status check failed for #%s: %s", claim_number, e)
            self.is_denied = False

        self.set_persona(
            organization_name="Ridgeline Health",
            agent_name="Taylor",
            agent_purpose=(
                "to inform patients about insurance claim decisions and help them understand "
                "their options, including how to appeal a denial"
            ),
        )

        self.reach_person(
            contact_full_name=patient_name,
            on_success=self.notify_patient,
            on_failure=self.recipient_unavailable,
        )

    def notify_patient(self):
        if not self.is_denied:
            # Claim is not (or no longer) denied — no action needed
            logging.info(
                "Claim #%s is not in a denied state for %s — ending call",
                self.claim_number, self.patient_name,
            )
            self.hangup(
                final_instructions=(
                    f"Greet {self.patient_name} from Ridgeline Health. "
                    f"Let them know you were calling about claim #{self.claim_number} for "
                    f"{self.service_description}, but it looks like it's no longer showing "
                    "as denied in our system. Apologize for any confusion and let them know "
                    "their billing team will send an updated summary by mail. Thank them."
                )
            )
            return

        self.set_task(
            objective=(
                f"Inform {self.patient_name} that their insurance claim #{self.claim_number} "
                f"for {self.service_description} was denied, explain why, and help them "
                "decide on next steps."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.patient_name}, this is Taylor calling from Ridgeline Health billing. "
                    f"I'm calling about your insurance claim #{self.claim_number} for "
                    f"{self.service_description}. Unfortunately, your insurance company has "
                    f"issued a decision of: {self.denial_description}. "
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
            on_complete=self.handle_next_steps,
        )

    def handle_next_steps(self):
        next_step = self.get_field("next_step_preference") or ""
        logging.info(
            "Denial next step for %s (claim #%s): %s",
            self.patient_name, self.claim_number, next_step,
        )

        if "appeal" in next_step:
            self.hangup(
                final_instructions=(
                    f"Let {self.patient_name} know that filing an appeal is their right. "
                    "Explain that our billing team will prepare an appeal letter on their behalf "
                    "and submit it to the insurer — this typically takes 5–7 business days. "
                    "Let them know they'll receive a written notice from us with the appeal details. "
                    "Thank them for their patience and for working with us on this."
                )
            )
        elif "payment plan" in next_step:
            self.hangup(
                final_instructions=(
                    f"Let {self.patient_name} know our billing team will reach out within two "
                    "business days to set up a payment plan that works for their situation. "
                    "Assure them we have flexible options available. "
                    "Thank them for their understanding."
                )
            )
        elif "billing review" in next_step:
            self.hangup(
                final_instructions=(
                    f"Let {self.patient_name} know a billing specialist will review their claim "
                    "and call them back within one business day with findings. "
                    "Thank them for their patience."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    f"Let {self.patient_name} know a billing specialist will call them back "
                    "within one business day to walk through all available options. "
                    "Provide Ridgeline Health's billing phone number if asked. "
                    "Thank them for taking the time to speak with us."
                )
            )

    def recipient_unavailable(self):
        logging.info(
            "Unable to reach %s for claim denial notification (claim #%s)",
            self.patient_name, self.claim_number,
        )
        self.hangup(
            final_instructions=(
                f"Leave a brief, professional voicemail for {self.patient_name} on behalf of "
                "Ridgeline Health billing. Let them know you're calling about a claim decision "
                f"on claim #{self.claim_number} for {self.service_description} and ask them "
                "to call back at their convenience to discuss next steps. "
                "Keep it concise and non-alarming."
            )
        )


if __name__ == "__main__":
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

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=ClaimDenialNotificationController(
            patient_name=args.name,
            first_name=args.first_name,
            last_name=args.last_name,
            date_of_birth=args.dob,
            member_id=args.member_id,
            payer_id=args.payer_id,
            claim_number=args.claim_number,
            service_description=args.service,
        ),
    )

import guava
import os
import logging
import json
import argparse
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


def submit_professional_claim(claim_payload: dict) -> dict:
    """Submits a professional (837P) claim to Change Healthcare."""
    token = get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    resp = requests.post(
        f"{BASE_URL}/medicalnetwork/professionalclaims/v3",
        headers=headers,
        json=claim_payload,
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


def build_claim_payload(
    provider_npi: str,
    provider_tax_id: str,
    payer_id: str,
    member_id: str,
    patient_first: str,
    patient_last: str,
    patient_dob: str,
    diagnosis_code: str,
    procedure_code: str,
    service_date: str,
    charge_amount: str,
) -> dict:
    control_number = datetime.utcnow().strftime("%H%M%S%f")[:9]
    return {
        "controlNumber": control_number,
        "tradingPartnerServiceId": payer_id,
        "submitter": {
            "organizationName": "Valley Medical Group",
            "contactInformation": {"name": "Billing Department"},
        },
        "receiver": {"organizationName": payer_id},
        "subscriber": {
            "memberId": member_id,
            "firstName": patient_first,
            "lastName": patient_last,
            "dateOfBirth": patient_dob,
        },
        "claimInformation": {
            "claimFilingCode": "CI",
            "patientControlNumber": f"VMG-{control_number}",
            "claimChargeAmount": charge_amount,
            "serviceLocationInfo": {"facilityCodeValue": "11"},
            "healthCareCodeInformation": [
                {"diagnosisTypeCode": "ABK", "diagnosisCode": diagnosis_code}
            ],
            "serviceFacilityLocation": {
                "organizationName": "Valley Medical Group",
                "npi": provider_npi,
            },
            "serviceLines": [
                {
                    "serviceDate": service_date,
                    "professionalService": {
                        "procedureCode": procedure_code,
                        "lineItemChargeAmount": charge_amount,
                        "measurementUnit": "UN",
                        "serviceUnitCount": "1",
                        "diagnosisCodePointers": ["1"],
                    },
                }
            ],
        },
        "providers": [
            {
                "providerType": "BillingProvider",
                "npi": provider_npi,
                "employerId": provider_tax_id,
                "organizationName": "Valley Medical Group",
            }
        ],
    }


class ClaimSubmissionTriggerController(guava.CallController):
    def __init__(self, patient_name: str, appointment_id: str):
        super().__init__()
        self.patient_name = patient_name
        self.appointment_id = appointment_id

        self.set_persona(
            organization_name="Valley Medical Group Billing",
            agent_name="Casey",
            agent_purpose=(
                "to confirm clinical and billing details with providers before submitting "
                "an insurance claim on their behalf"
            ),
        )

        self.reach_person(
            contact_full_name=self.patient_name,
            on_success=self.begin_confirmation,
            on_failure=self.recipient_unavailable,
        )

    def begin_confirmation(self):
        self.set_task(
            objective=(
                f"Confirm billing information for a recent visit by {self.patient_name} "
                f"(appointment {self.appointment_id}) before submitting the claim."
            ),
            checklist=[
                guava.Say(
                    f"Hi, this is Casey calling from Valley Medical Group billing. "
                    f"I'm reaching out to confirm a few details for {self.patient_name}'s "
                    f"recent visit before we submit the insurance claim. This will only take "
                    "a moment — I just have a few quick questions."
                ),
                guava.Field(
                    key="diagnosis_confirmed",
                    field_type="multiple_choice",
                    description=(
                        "Confirm that the diagnosis and service information on file is correct. "
                        "Ask if they can verify the visit details are accurate to the best of "
                        "their knowledge."
                    ),
                    choices=["yes, confirmed", "no, there is an issue"],
                    required=True,
                ),
                guava.Field(
                    key="insurance_active",
                    field_type="multiple_choice",
                    description=(
                        "Ask if the patient's insurance coverage was active at the time of "
                        "the visit."
                    ),
                    choices=["yes", "no", "unsure"],
                    required=True,
                ),
                guava.Field(
                    key="additional_notes",
                    field_type="text",
                    description=(
                        "Ask if there are any additional billing notes or circumstances "
                        "we should be aware of before submitting the claim. Capture anything relevant."
                    ),
                    required=False,
                ),
            ],
            on_complete=self.submit_claim,
        )

    def submit_claim(self):
        confirmed = self.get_field("diagnosis_confirmed")
        insurance_active = self.get_field("insurance_active")
        notes = self.get_field("additional_notes") or ""

        if confirmed != "yes, confirmed" or insurance_active == "no":
            logging.warning(
                "Claim submission held for appointment %s — confirmation issue: %s, insurance: %s",
                self.appointment_id, confirmed, insurance_active,
            )
            print(json.dumps({
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "appointment_id": self.appointment_id,
                "action": "held_for_review",
                "reason": f"confirmation={confirmed}, insurance_active={insurance_active}",
                "notes": notes,
            }, indent=2))
            self.hangup(
                final_instructions=(
                    f"Let the caller know that we've put the claim for {self.patient_name} "
                    "on hold for review by our billing team. A billing specialist will follow "
                    "up within one business day to resolve the discrepancy. "
                    "Thank them for their time."
                )
            )
            return

        provider_npi = os.environ["PROVIDER_NPI"]
        provider_tax_id = os.environ["PROVIDER_TAX_ID"]
        payer_id = os.environ.get("CHANGE_HEALTHCARE_TRADING_PARTNER_ID", "000050")
        # These would normally come from the appointment/EHR record
        member_id = os.environ.get("DEMO_MEMBER_ID", "MBR123456")
        patient_first = self.patient_name.split()[0] if self.patient_name else "Patient"
        patient_last = self.patient_name.split()[-1] if self.patient_name else "Unknown"
        diagnosis_code = os.environ.get("DEMO_DIAGNOSIS_CODE", "Z00.00")
        procedure_code = os.environ.get("DEMO_PROCEDURE_CODE", "99213")
        service_date = os.environ.get("DEMO_SERVICE_DATE", datetime.utcnow().strftime("%Y-%m-%d"))
        charge_amount = os.environ.get("DEMO_CHARGE_AMOUNT", "150.00")

        payload = build_claim_payload(
            provider_npi=provider_npi,
            provider_tax_id=provider_tax_id,
            payer_id=payer_id,
            member_id=member_id,
            patient_first=patient_first,
            patient_last=patient_last,
            patient_dob=os.environ.get("DEMO_PATIENT_DOB", "1985-06-15"),
            diagnosis_code=diagnosis_code,
            procedure_code=procedure_code,
            service_date=service_date,
            charge_amount=charge_amount,
        )

        try:
            response = submit_professional_claim(payload)
            claim_id = response.get("claimReference", {}).get("correlationId", "")
            logging.info("Claim submitted for appointment %s — ID: %s", self.appointment_id, claim_id)

            print(json.dumps({
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "appointment_id": self.appointment_id,
                "patient_name": self.patient_name,
                "action": "claim_submitted",
                "claim_id": claim_id,
                "notes": notes,
            }, indent=2))

            self.hangup(
                final_instructions=(
                    f"Let the caller know that the insurance claim for {self.patient_name}'s "
                    f"visit has been submitted successfully. The claim reference ID is {claim_id}. "
                    "Processing typically takes 5 to 10 business days. "
                    "Thank them for their time and for helping us keep billing accurate."
                )
            )
        except Exception as e:
            logging.error("Claim submission failed for appointment %s: %s", self.appointment_id, e)
            self.hangup(
                final_instructions=(
                    f"Apologize for a technical issue and let the caller know the claim for "
                    f"{self.patient_name} could not be submitted at this time. "
                    "Our billing team will retry submission and follow up if any action is needed. "
                    "Thank them for their time."
                )
            )

    def recipient_unavailable(self):
        logging.info("Unable to reach contact for appointment %s", self.appointment_id)
        self.hangup(
            final_instructions=(
                "Leave a brief voicemail on behalf of Valley Medical Group billing. "
                "Let them know we were calling to confirm visit details before submitting "
                "an insurance claim, and that we'll attempt to reach them again. "
                "Provide the billing department callback number."
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Outbound call to confirm billing details before claim submission."
    )
    parser.add_argument("phone", help="Contact phone number (E.164, e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Patient full name")
    parser.add_argument("--appointment-id", required=True, help="Appointment or encounter ID")
    args = parser.parse_args()

    logging.info(
        "Initiating claim submission confirmation call to %s for appointment %s",
        args.name, args.appointment_id,
    )

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=ClaimSubmissionTriggerController(
            patient_name=args.name,
            appointment_id=args.appointment_id,
        ),
    )

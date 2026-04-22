import argparse
import json
import logging
import os
from datetime import datetime, timezone

import guava
import requests
from guava import logging_utils

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
    control_number = datetime.now(timezone.utc).strftime("%H%M%S%f")[:9]
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


agent = guava.Agent(
    name="Casey",
    organization="Valley Medical Group Billing",
    purpose=(
        "to confirm clinical and billing details with providers before submitting "
        "an insurance claim on their behalf"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(contact_full_name=call.get_variable("patient_name"))


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    if outcome == "unavailable":
        logging.info(
            "Unable to reach contact for appointment %s",
            call.get_variable("appointment_id"),
        )
        call.hangup(
            final_instructions=(
                "Leave a brief voicemail on behalf of Valley Medical Group billing. "
                "Let them know we were calling to confirm visit details before submitting "
                "an insurance claim, and that we'll attempt to reach them again. "
                "Provide the billing department callback number."
            )
        )
    elif outcome == "available":
        patient_name = call.get_variable("patient_name")
        appointment_id = call.get_variable("appointment_id")
        call.set_task(
            "confirm_and_submit_claim",
            objective=(
                f"Confirm billing information for a recent visit by {patient_name} "
                f"(appointment {appointment_id}) before submitting the claim."
            ),
            checklist=[
                guava.Say(
                    f"Hi, this is Casey calling from Valley Medical Group billing. "
                    f"I'm reaching out to confirm a few details for {patient_name}'s "
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
        )


@agent.on_task_complete("confirm_and_submit_claim")
def on_confirm_and_submit_claim(call: guava.Call) -> None:
    patient_name = call.get_variable("patient_name")
    appointment_id = call.get_variable("appointment_id")
    confirmed = call.get_field("diagnosis_confirmed")
    insurance_active = call.get_field("insurance_active")
    notes = call.get_field("additional_notes") or ""

    if confirmed != "yes, confirmed" or insurance_active == "no":
        logging.warning(
            "Claim submission held for appointment %s — confirmation issue: %s, insurance: %s",
            appointment_id, confirmed, insurance_active,
        )
        print(json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "appointment_id": appointment_id,
            "action": "held_for_review",
            "reason": f"confirmation={confirmed}, insurance_active={insurance_active}",
            "notes": notes,
        }, indent=2))
        call.hangup(
            final_instructions=(
                f"Let the caller know that we've put the claim for {patient_name} "
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
    patient_first = patient_name.split()[0] if patient_name else "Patient"
    patient_last = patient_name.split()[-1] if patient_name else "Unknown"
    diagnosis_code = os.environ.get("DEMO_DIAGNOSIS_CODE", "Z00.00")
    procedure_code = os.environ.get("DEMO_PROCEDURE_CODE", "99213")
    service_date = os.environ.get("DEMO_SERVICE_DATE", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
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
        logging.info("Claim submitted for appointment %s — ID: %s", appointment_id, claim_id)

        print(json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "appointment_id": appointment_id,
            "patient_name": patient_name,
            "action": "claim_submitted",
            "claim_id": claim_id,
            "notes": notes,
        }, indent=2))

        call.hangup(
            final_instructions=(
                f"Let the caller know that the insurance claim for {patient_name}'s "
                f"visit has been submitted successfully. The claim reference ID is {claim_id}. "
                "Processing typically takes 5 to 10 business days. "
                "Thank them for their time and for helping us keep billing accurate."
            )
        )
    except Exception as e:
        logging.error("Claim submission failed for appointment %s: %s", appointment_id, e)
        call.hangup(
            final_instructions=(
                f"Apologize for a technical issue and let the caller know the claim for "
                f"{patient_name} could not be submitted at this time. "
                "Our billing team will retry submission and follow up if any action is needed. "
                "Thank them for their time."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
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

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "patient_name": args.name,
            "appointment_id": args.appointment_id,
        },
    )

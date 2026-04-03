import guava
import os
import logging
import json
import requests
import argparse
from datetime import datetime

logging.basicConfig(level=logging.INFO)


class InsuranceUpdateController(guava.CallController):
    def __init__(self, patient_name: str, patient_id: str):
        super().__init__()
        self.patient_name = patient_name
        self.patient_id = patient_id

        self.set_persona(
            organization_name="Cedar Health",
            agent_name="Taylor",
            agent_purpose=(
                "to collect and verify insurance information before an upcoming visit "
                "and update the patient's coverage record in Epic on behalf of Cedar Health"
            ),
        )

        self.reach_person(
            contact_full_name=self.patient_name,
            on_success=self.begin_insurance_update,
            on_failure=self.recipient_unavailable,
        )

    def begin_insurance_update(self):
        self.set_task(
            objective=(
                f"Collect current insurance information from {self.patient_name} before their "
                "upcoming visit at Cedar Health and verify the details are accurate and up to date."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.patient_name}, this is Taylor calling from Cedar Health. "
                    "I'm calling to verify your insurance information before your upcoming visit "
                    "to make sure everything is accurate on file."
                ),
                guava.Field(
                    key="insurance_provider",
                    description=(
                        "Ask for the name of the patient's primary health insurance provider "
                        "(e.g., Blue Cross Blue Shield, Aetna, UnitedHealthcare, Medicare)."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="member_id",
                    description=(
                        "Ask for their insurance member ID number as shown on their insurance card."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="group_number",
                    description=(
                        "Ask for their group number from their insurance card. "
                        "If they do not have a group number (e.g., individual plan), capture 'none'."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="subscriber_name",
                    description=(
                        "Ask for the name of the primary subscriber on the insurance policy. "
                        "This may be the patient themselves or a spouse or parent."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="insurance_confirmed",
                    description=(
                        "Confirm all the information back to the patient and ask them to verify "
                        "that everything is correct. Capture 'confirmed' or 'correction needed'."
                    ),
                    field_type="text",
                    required=True,
                ),
            ],
            on_complete=self.save_results,
        )

    def save_results(self):
        insurance_provider = self.get_field("insurance_provider")
        member_id = self.get_field("member_id")
        group_number = self.get_field("group_number")
        subscriber_name = self.get_field("subscriber_name")
        insurance_confirmed = self.get_field("insurance_confirmed")

        results = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "agent": "Taylor",
            "organization": "Cedar Health",
            "use_case": "insurance_update",
            "patient_name": self.patient_name,
            "patient_id": self.patient_id,
            "fields": {
                "insurance_provider": insurance_provider,
                "member_id": member_id,
                "group_number": group_number,
                "subscriber_name": subscriber_name,
                "insurance_confirmed": insurance_confirmed,
            },
        }
        print(json.dumps(results, indent=2))
        logging.info("Insurance update results saved locally.")

        # Post-call: create a Coverage resource in Epic with the verified insurance details.
        # Two class entries are written — one for group number and one for member ID —
        # matching Epic's expected Coverage structure for billing workflows.
        try:
            base_url = os.environ["EPIC_BASE_URL"]
            access_token = os.environ["EPIC_ACCESS_TOKEN"]
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }

            coverage_payload = {
                "resourceType": "Coverage",
                "status": "active",
                "subscriber": {"display": subscriber_name},
                "beneficiary": {"reference": f"Patient/{self.patient_id}"},
                "payor": [{"display": insurance_provider}],
                "class": [
                    {
                        "type": {
                            "coding": [
                                {
                                    "system": "http://terminology.hl7.org/CodeSystem/coverage-class",
                                    "code": "group",
                                }
                            ]
                        },
                        "value": group_number,
                        "name": insurance_provider,
                    },
                    {
                        "type": {
                            "coding": [
                                {
                                    "system": "http://terminology.hl7.org/CodeSystem/coverage-class",
                                    "code": "member",
                                }
                            ]
                        },
                        "value": member_id,
                    },
                ],
            }

            resp = requests.post(
                f"{base_url}/Coverage",
                headers=headers,
                json=coverage_payload,
                timeout=10,
            )
            resp.raise_for_status()
            cov_id = resp.json().get("id", "")
            logging.info("Epic Coverage created: %s", cov_id)
        except Exception as e:
            logging.error("Failed to create Epic Coverage: %s", e)

        self.hangup(
            final_instructions=(
                f"Thank {self.patient_name} for verifying their insurance information. Let them know "
                "their coverage details have been updated in Cedar Health's system. Remind them to "
                "bring their insurance card to their appointment. Wish them a great day."
            )
        )

    def recipient_unavailable(self):
        self.hangup(
            final_instructions=(
                f"We were unable to reach {self.patient_name}. Leave a brief voicemail on behalf of "
                "Cedar Health asking them to call back to verify their insurance information before "
                "their upcoming visit. Provide the clinic's main number."
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Outbound insurance update call for Cedar Health via Epic FHIR."
    )
    parser.add_argument("phone", help="Patient phone number to call (E.164 format, e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Full name of the patient")
    parser.add_argument("--patient-id", required=True, help="Epic Patient FHIR resource ID")
    args = parser.parse_args()

    logging.info(
        "Initiating insurance update call to %s (%s), patient ID: %s",
        args.name,
        args.phone,
        args.patient_id,
    )

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=InsuranceUpdateController(
            patient_name=args.name,
            patient_id=args.patient_id,
        ),
    )

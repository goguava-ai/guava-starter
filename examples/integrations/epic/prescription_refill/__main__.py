import guava
import os
import logging
from guava import logging_utils
import json
import requests
import argparse
from datetime import datetime, timezone



class PrescriptionRefillController(guava.CallController):
    def __init__(self, patient_name: str, patient_id: str, medication: str):
        super().__init__()
        self.patient_name = patient_name
        self.patient_id = patient_id
        self.medication = medication

        self.set_persona(
            organization_name="Cedar Health",
            agent_name="Jordan",
            agent_purpose=(
                f"to confirm a prescription refill for {medication} and submit the refill "
                "request to Epic on behalf of Cedar Health pharmacy services"
            ),
        )

        self.reach_person(
            contact_full_name=self.patient_name,
            on_success=self.begin_refill,
            on_failure=self.recipient_unavailable,
        )

    def begin_refill(self):
        self.set_task(
            objective=(
                f"Confirm whether {self.patient_name} would like to refill their prescription "
                f"for {self.medication}. Collect their preferred pharmacy and any questions "
                "for the pharmacist or care team."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.patient_name}, this is Jordan calling from Cedar Health pharmacy services. "
                    f"I'm reaching out because a refill is available for your prescription of {self.medication}."
                ),
                guava.Field(
                    key="confirm_refill",
                    description=(
                        f"Ask whether the patient would like to go ahead with the refill of {self.medication}. "
                        "Capture 'yes' or 'no'."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="preferred_pharmacy",
                    description=(
                        "If they confirmed the refill, ask for their preferred pharmacy name and location "
                        "where they would like the prescription sent. Skip if they declined the refill."
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="questions_for_pharmacist",
                    description=(
                        "Ask if the patient has any questions about this medication or their dosage "
                        "that they would like passed along to the pharmacist or prescribing provider. "
                        "Skip if they have none."
                    ),
                    field_type="text",
                    required=False,
                ),
            ],
            on_complete=self.save_results,
        )

    def save_results(self):
        confirm_refill = self.get_field("confirm_refill")
        preferred_pharmacy = self.get_field("preferred_pharmacy")
        questions = self.get_field("questions_for_pharmacist")

        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": "Jordan",
            "organization": "Cedar Health",
            "use_case": "prescription_refill",
            "patient_name": self.patient_name,
            "patient_id": self.patient_id,
            "medication": self.medication,
            "fields": {
                "confirm_refill": confirm_refill,
                "preferred_pharmacy": preferred_pharmacy,
                "questions_for_pharmacist": questions,
            },
        }
        print(json.dumps(results, indent=2))
        logging.info("Prescription refill results saved locally.")

        # Post-call: only write to Epic if the patient actually confirmed the refill —
        # no point creating a MedicationRequest for a refill the patient declined.
        confirmed = confirm_refill and confirm_refill.strip().lower() == "yes"
        if confirmed:
            try:
                base_url = os.environ["EPIC_BASE_URL"]
                access_token = os.environ["EPIC_ACCESS_TOKEN"]
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                }

                med_request_payload = {
                    "resourceType": "MedicationRequest",
                    "status": "active",
                    "intent": "order",
                    "medicationCodeableConcept": {
                        "text": self.medication,
                    },
                    "subject": {"reference": f"Patient/{self.patient_id}"},
                    "authoredOn": datetime.now(timezone.utc).isoformat(),
                    "note": [
                        {
                            "text": (
                                f"Refill requested via voice confirmation. "
                                f"Pharmacy: {preferred_pharmacy or 'Not specified'}. "
                                f"Patient questions: {questions or 'None'}."
                            )
                        }
                    ],
                }

                resp = requests.post(
                    f"{base_url}/MedicationRequest",
                    headers=headers,
                    json=med_request_payload,
                    timeout=10,
                )
                resp.raise_for_status()
                req_id = resp.json().get("id", "")
                logging.info("Epic MedicationRequest created: %s", req_id)
            except Exception as e:
                logging.error("Failed to create Epic MedicationRequest: %s", e)

        if confirmed:
            self.hangup(
                final_instructions=(
                    f"Let {self.patient_name} know their refill request for {self.medication} has been submitted "
                    f"and will be sent to {preferred_pharmacy or 'their pharmacy on file'}. "
                    "Let them know it is typically ready within 24 hours. "
                    "If they had questions, confirm those will be passed along to their care team. "
                    "Thank them and wish them a great day."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    f"Acknowledge that {self.patient_name} does not need the refill at this time. "
                    "Let them know they can call Cedar Health pharmacy services whenever they are ready. "
                    "Thank them and wish them a great day."
                )
            )

    def recipient_unavailable(self):
        self.hangup(
            final_instructions=(
                f"We were unable to reach {self.patient_name}. Leave a brief voicemail on behalf of "
                "Cedar Health pharmacy services letting them know a refill is available for "
                f"{self.medication} and asking them to call back to confirm."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound prescription refill confirmation call for Cedar Health via Epic FHIR."
    )
    parser.add_argument("phone", help="Patient phone number to call (E.164 format, e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Full name of the patient")
    parser.add_argument("--patient-id", required=True, help="Epic Patient FHIR resource ID")
    parser.add_argument("--medication", required=True, help="Name of the medication to refill")
    args = parser.parse_args()

    logging.info(
        "Initiating prescription refill call to %s (%s) for medication: %s",
        args.name,
        args.phone,
        args.medication,
    )

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=PrescriptionRefillController(
            patient_name=args.name,
            patient_id=args.patient_id,
            medication=args.medication,
        ),
    )

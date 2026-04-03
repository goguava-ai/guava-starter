import guava
import os
import logging
import json
import requests
import argparse
from datetime import datetime

logging.basicConfig(level=logging.INFO)


class LabResultsNotificationController(guava.CallController):
    def __init__(self, patient_name: str, patient_id: str, report_id: str):
        super().__init__()
        self.patient_name = patient_name
        self.patient_id = patient_id
        self.report_id = report_id
        self.report_summary = "your recent lab results"

        # Pre-call: fetch the DiagnosticReport to get the result type (e.g. "Complete Blood Count").
        # This lets the agent say "your CBC results are available" instead of a generic message.
        try:
            base_url = os.environ["EPIC_BASE_URL"]
            access_token = os.environ["EPIC_ACCESS_TOKEN"]
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }
            resp = requests.get(
                f"{base_url}/DiagnosticReport/{report_id}",
                headers=headers,
                timeout=10,
            )
            resp.raise_for_status()
            report = resp.json()
            code_text = report.get("code", {}).get("text", "")
            if code_text:
                self.report_summary = f"your {code_text} results"
        except Exception as e:
            logging.error("Failed to fetch Epic DiagnosticReport: %s", e)

        self.set_persona(
            organization_name="Cedar Health",
            agent_name="Alex",
            agent_purpose=(
                "to notify patients that their lab results are available and log "
                "their acknowledgment in Epic on behalf of Cedar Health"
            ),
        )

        self.reach_person(
            contact_full_name=self.patient_name,
            on_success=self.begin_notification,
            on_failure=self.recipient_unavailable,
        )

    def begin_notification(self):
        self.set_task(
            objective=(
                f"Notify {self.patient_name} that {self.report_summary} are available in their "
                "patient portal, confirm they acknowledge receipt, and determine if they have "
                "questions for their provider."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.patient_name}, this is Alex calling from Cedar Health. "
                    f"I'm calling to let you know that {self.report_summary} are now available "
                    "in your patient portal."
                ),
                guava.Field(
                    key="acknowledged",
                    description=(
                        "Confirm the patient heard and acknowledges that their lab results are available. "
                        "Capture 'yes' when they confirm receipt."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="has_questions",
                    description=(
                        "Ask if the patient has any questions about their results that they would "
                        "like to discuss with their provider. Capture 'yes' or 'no'."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="callback_requested",
                    description=(
                        "If the patient has questions, ask if they would like a callback from their "
                        "provider to review the results. Capture 'yes' or 'no'. "
                        "Skip if they said they have no questions."
                    ),
                    field_type="text",
                    required=False,
                ),
            ],
            on_complete=self.save_results,
        )

    def save_results(self):
        acknowledged = self.get_field("acknowledged")
        has_questions = self.get_field("has_questions")
        callback_requested = self.get_field("callback_requested")

        results = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "agent": "Alex",
            "organization": "Cedar Health",
            "use_case": "lab_results_notification",
            "patient_name": self.patient_name,
            "patient_id": self.patient_id,
            "report_id": self.report_id,
            "fields": {
                "acknowledged": acknowledged,
                "has_questions": has_questions,
                "callback_requested": callback_requested,
            },
        }
        print(json.dumps(results, indent=2))
        logging.info("Lab results notification results saved locally.")

        # Post-call: log a Communication resource in Epic to record that the patient
        # was notified, whether they acknowledged, and whether they want a callback.
        # This creates an auditable trail of patient outreach in the chart.
        try:
            base_url = os.environ["EPIC_BASE_URL"]
            access_token = os.environ["EPIC_ACCESS_TOKEN"]
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }

            comm_payload = {
                "resourceType": "Communication",
                "status": "completed",
                "subject": {"reference": f"Patient/{self.patient_id}"},
                "sent": datetime.utcnow().isoformat() + "Z",
                "payload": [
                    {
                        "contentString": (
                            f"Lab results notification for report {self.report_id}. "
                            f"Patient acknowledged: {acknowledged}. "
                            f"Has questions: {has_questions}. "
                            f"Callback requested: {callback_requested or 'N/A'}."
                        )
                    }
                ],
            }

            resp = requests.post(
                f"{base_url}/Communication",
                headers=headers,
                json=comm_payload,
                timeout=10,
            )
            resp.raise_for_status()
            comm_id = resp.json().get("id", "")
            logging.info("Epic Communication created: %s", comm_id)
        except Exception as e:
            logging.error("Failed to create Epic Communication: %s", e)

        # Close with instructions that match whether a provider callback was requested
        wants_callback = callback_requested and callback_requested.strip().lower() == "yes"
        if wants_callback:
            self.hangup(
                final_instructions=(
                    f"Let {self.patient_name} know that a member of their care team at Cedar Health "
                    "will call them back to review their results. Provide the clinic's main number "
                    "in case they need to reach someone sooner. Thank them and wish them a great day."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    f"Let {self.patient_name} know they can view their full results in the Cedar Health "
                    "patient portal anytime, and they are welcome to call the clinic if any questions "
                    "come up later. Thank them and wish them a great day."
                )
            )

    def recipient_unavailable(self):
        self.hangup(
            final_instructions=(
                "We were unable to reach the patient. Leave a brief voicemail on behalf of Cedar Health "
                "letting them know their lab results are available in their patient portal and they "
                "can call the clinic if they have any questions."
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Outbound lab results notification call for Cedar Health via Epic FHIR."
    )
    parser.add_argument("phone", help="Patient phone number to call (E.164 format, e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Full name of the patient")
    parser.add_argument("--patient-id", required=True, help="Epic Patient FHIR resource ID")
    parser.add_argument("--report-id", required=True, help="Epic DiagnosticReport FHIR resource ID")
    args = parser.parse_args()

    logging.info(
        "Initiating lab results notification call to %s (%s) for report %s",
        args.name,
        args.phone,
        args.report_id,
    )

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=LabResultsNotificationController(
            patient_name=args.name,
            patient_id=args.patient_id,
            report_id=args.report_id,
        ),
    )

import guava
import os
import logging
import argparse
import requests
from datetime import datetime

logging.basicConfig(level=logging.INFO)

BASE_URL = os.environ.get("PRACTICE_FUSION_FHIR_BASE_URL", "https://api.practicefusion.com/fhir/r4")


def get_headers():
    return {
        "Authorization": f"Bearer {os.environ['PRACTICE_FUSION_ACCESS_TOKEN']}",
        "Content-Type": "application/json",
    }


def get_diagnostic_report(report_id: str) -> dict:
    """Fetch a single DiagnosticReport resource by ID."""
    resp = requests.get(
        f"{BASE_URL}/DiagnosticReport/{report_id}",
        headers=get_headers(),
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def classify_report(report: dict) -> tuple[str, str]:
    """
    Return a (test_name, overall_status_phrase) tuple for the agent to speak.

    The overall_status_phrase is a high-level plain-language summary:
    'all values within normal range' or 'some values outside the normal range'.
    Determination is based on the DiagnosticReport.conclusion field when present,
    otherwise the presence of any abnormal-coded result observations is checked.
    """
    # Extract the human-readable test name from code.text or first coding.display
    code = report.get("code", {})
    test_name = code.get("text", "")
    if not test_name:
        for coding in code.get("coding", []):
            if coding.get("display"):
                test_name = coding["display"]
                break
    if not test_name:
        test_name = "lab panel"

    # Use the free-text conclusion as the primary signal when available.
    conclusion = report.get("conclusion", "").lower()
    if conclusion:
        abnormal_keywords = ["abnormal", "elevated", "low", "high", "outside", "flag", "critical"]
        if any(kw in conclusion for kw in abnormal_keywords):
            status_phrase = "some values outside the normal range"
        else:
            status_phrase = "all values within the normal range"
        return test_name, status_phrase

    # Fall back to checking conclusionCode codings for abnormal SNOMED/LOINC codes.
    for concept in report.get("conclusionCode", []):
        for coding in concept.get("coding", []):
            code_val = coding.get("code", "").lower()
            display_val = coding.get("display", "").lower()
            if "abnormal" in code_val or "abnormal" in display_val:
                return test_name, "some values outside the normal range"

    return test_name, "all values within the normal range"


def log_communication(patient_id: str, report_id: str, acknowledged: str, questions_noted: str) -> dict:
    """
    POST a Communication resource to Practice Fusion to record that the patient
    was notified of their results and whether they had questions.
    """
    payload = {
        "resourceType": "Communication",
        "status": "completed",
        "subject": {"reference": f"Patient/{patient_id}"},
        "sent": datetime.utcnow().isoformat() + "Z",
        "payload": [
            {
                "contentString": (
                    f"Lab results callback for DiagnosticReport/{report_id}. "
                    f"Patient acknowledged results: {acknowledged}. "
                    f"Patient had questions for provider: {questions_noted}."
                )
            }
        ],
    }
    resp = requests.post(
        f"{BASE_URL}/Communication",
        headers=get_headers(),
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


class LabResultsCallbackController(guava.CallController):
    def __init__(self, patient_name: str, patient_id: str, report_id: str):
        super().__init__()
        self.patient_name = patient_name
        self.patient_id = patient_id
        self.report_id = report_id
        self._test_name = "your recent lab panel"
        self._status_phrase = "results are available"

        # Pre-call: fetch the DiagnosticReport so the agent can describe the test
        # type and convey a high-level normal/abnormal summary.
        try:
            report = get_diagnostic_report(report_id)
            test_name, status_phrase = classify_report(report)
            self._test_name = test_name
            self._status_phrase = status_phrase
            logging.info(
                "DiagnosticReport %s: test=%s, status=%s",
                report_id,
                test_name,
                status_phrase,
            )
        except Exception as exc:
            logging.error("Failed to fetch DiagnosticReport %s: %s", report_id, exc)

        self.set_persona(
            organization_name="Westfield Medical Group",
            agent_name="Riley",
            agent_purpose=(
                "to notify patients that their lab results are ready, provide a high-level summary "
                "of whether values are normal or abnormal, answer general questions, and log "
                "acknowledgment in Practice Fusion"
            ),
        )

        self.reach_person(
            contact_full_name=self.patient_name,
            on_success=self.deliver_results,
            on_failure=self.leave_voicemail,
        )

    def deliver_results(self):
        self.set_task(
            objective=(
                f"Notify {self.patient_name} that their {self._test_name} results are ready. "
                f"The high-level summary is: {self._status_phrase}. "
                "Convey this in plain, reassuring language. Do not read raw codes or numeric values. "
                "If values are outside the normal range, let the patient know their provider will "
                "review the results and follow up with next steps. "
                "Answer general questions but do not interpret specific clinical values."
            ),
            checklist=[
                guava.Say(
                    f"Hello {self.patient_name}, this is Riley calling from Westfield Medical Group. "
                    f"I'm reaching out because your {self._test_name} results are now available."
                ),
                guava.Field(
                    key="acknowledged",
                    field_type="multiple_choice",
                    description=(
                        f"Let the patient know the overall status: {self._status_phrase}. "
                        "Ask if they acknowledge receiving this update."
                    ),
                    choices=["yes", "no"],
                    required=True,
                ),
                guava.Field(
                    key="has_questions",
                    field_type="multiple_choice",
                    description=(
                        "Ask whether the patient has any questions about their results that they "
                        "would like passed along to their provider."
                    ),
                    choices=["yes", "no"],
                    required=True,
                ),
                guava.Field(
                    key="question_details",
                    field_type="text",
                    description=(
                        "If the patient has questions, ask them to describe what they would like to "
                        "know so the information can be passed to their care team. "
                        "Only collect this if they said yes."
                    ),
                    required=False,
                ),
            ],
            on_complete=self.handle_outcome,
        )

    def handle_outcome(self):
        acknowledged = self.get_field("acknowledged") or "yes"
        has_questions = self.get_field("has_questions") or "no"
        question_details = self.get_field("question_details")

        # Log a Communication resource in Practice Fusion to record the outreach outcome.
        questions_noted = "yes" if has_questions.strip().lower() == "yes" else "no"
        try:
            comm = log_communication(
                self.patient_id,
                self.report_id,
                acknowledged,
                questions_noted,
            )
            logging.info("Communication resource created: %s", comm.get("id", "unknown"))
        except Exception as exc:
            logging.error("Failed to log Communication for patient %s: %s", self.patient_id, exc)

        if has_questions.strip().lower() == "yes":
            self.hangup(
                final_instructions=(
                    f"Let {self.patient_name} know their questions have been noted and a member of "
                    "their care team at Westfield Medical Group will call them back within one to two "
                    "business days to discuss their results in detail. "
                    "If they mentioned any specific concerns, acknowledge those warmly. "
                    "Thank them and wish them well."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    f"Thank {self.patient_name} for taking the call. Let them know they can view "
                    "their full results in the Westfield Medical Group patient portal at any time. "
                    "Remind them to reach out if any questions come up later. Wish them a great day."
                )
            )

    def leave_voicemail(self):
        self.hangup(
            final_instructions=(
                f"Leave a brief, professional voicemail for {self.patient_name} on behalf of "
                "Westfield Medical Group. Let them know we are calling because their recent lab "
                "results are available and ask them to call us back at their earliest convenience. "
                "Do not mention specific test names, values, or any clinical details. "
                "Keep the message under 30 seconds."
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Outbound lab results callback call for Westfield Medical Group via Practice Fusion FHIR R4."
    )
    parser.add_argument("phone", help="Patient phone number in E.164 format (e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Patient full name")
    parser.add_argument("--patient-id", required=True, help="Practice Fusion FHIR Patient resource ID")
    parser.add_argument("--report-id", required=True, help="Practice Fusion FHIR DiagnosticReport resource ID")
    args = parser.parse_args()

    logging.info(
        "Initiating lab results callback to %s (%s), report %s",
        args.name,
        args.phone,
        args.report_id,
    )

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=LabResultsCallbackController(
            patient_name=args.name,
            patient_id=args.patient_id,
            report_id=args.report_id,
        ),
    )

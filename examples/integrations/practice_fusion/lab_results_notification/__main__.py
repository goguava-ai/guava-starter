import guava
import os
import logging
import argparse
import requests
from datetime import datetime

logging.basicConfig(level=logging.INFO)

BASE_URL = os.environ["PRACTICE_FUSION_FHIR_BASE_URL"]  # e.g. https://api.practicefusion.com/fhir/r4


def get_headers():
    return {
        "Authorization": f"Bearer {os.environ['PRACTICE_FUSION_ACCESS_TOKEN']}",
        "Content-Type": "application/json",
    }


def get_recent_diagnostic_reports(patient_id: str, count: int = 5) -> list[dict]:
    """Fetch the most recent DiagnosticReport resources for a patient, sorted newest first."""
    url = f"{BASE_URL}/DiagnosticReport"
    params = {
        "patient": f"Patient/{patient_id}",
        "_sort": "-date",
        "_count": count,
    }
    response = requests.get(url, headers=get_headers(), params=params)
    response.raise_for_status()
    bundle = response.json()
    return [entry["resource"] for entry in bundle.get("entry", [])]


def summarize_reports(reports: list[dict]) -> str:
    """Build a brief plain-text summary of diagnostic report statuses for agent reference."""
    if not reports:
        return "No recent diagnostic reports found."

    lines = []
    for report in reports:
        report_id = report.get("id", "unknown")
        status = report.get("status", "unknown")
        code_text = (
            report.get("code", {})
            .get("text")
            or report.get("code", {})
            .get("coding", [{}])[0]
            .get("display", "Lab panel")
        )
        effective = report.get("effectiveDateTime", report.get("issued", ""))
        try:
            dt = datetime.fromisoformat(effective.replace("Z", "+00:00"))
            date_str = dt.strftime("%B %-d, %Y")
        except (ValueError, AttributeError):
            date_str = effective

        lines.append(f"- {code_text} ({date_str}): status={status}, id={report_id}")

    return "\n".join(lines)


class LabResultsController(guava.CallController):
    def __init__(self, patient_name: str, patient_id: str, result_summary: str):
        super().__init__()
        self.patient_name = patient_name
        self.patient_id = patient_id
        self.result_summary = result_summary
        self._report_detail = ""

        self.set_persona(
            organization_name="Riverside Family Medicine",
            agent_name="Sam",
            agent_purpose="to notify patients of their lab results",
        )

        self.reach_person(
            contact_full_name=self.patient_name,
            on_success=self.deliver_results,
            on_failure=self.leave_voicemail,
        )

    def _fetch_report_detail(self):
        """Fetch FHIR DiagnosticReports and store a plain-text summary for agent context."""
        try:
            reports = get_recent_diagnostic_reports(self.patient_id)
            self._report_detail = summarize_reports(reports)
            logging.info("Report detail fetched:\n%s", self._report_detail)
        except requests.HTTPError as exc:
            logging.error("Failed to fetch diagnostic reports: %s", exc)
            self._report_detail = self.result_summary  # fall back to CLI summary

    def deliver_results(self):
        self._fetch_report_detail()

        self.set_task(
            objective=(
                f"Inform {self.patient_name} that their recent lab results are available "
                f"and convey the following summary to guide the conversation: "
                f"{self._report_detail}. "
                f"Do not read raw status codes verbatim; translate them into plain language "
                f"(e.g., 'final' means the results are complete). "
                f"Do not disclose specific numeric values unless the summary explicitly includes them."
            ),
            checklist=[
                guava.Say(
                    f"Hi, may I please speak with {self.patient_name}?"
                ),
                guava.Say(
                    f"Hello {self.patient_name}, this is Sam calling from Riverside Family Medicine. "
                    f"I'm reaching out because your recent lab results are now available and ready to review."
                ),
                guava.Field(
                    key="has_questions",
                    field_type="multiple_choice",
                    description=(
                        "Let the patient know the general status of their results using the summary "
                        "provided. Then ask if they have any questions about the results."
                    ),
                    choices=["yes", "no"],
                    required=True,
                ),
            ],
            on_complete=self.wrap_up,
        )

    def wrap_up(self):
        has_questions = self.get_field("has_questions")
        if has_questions == "yes":
            self.hangup(
                final_instructions=(
                    f"Let {self.patient_name} know that a nurse or their care team will call them "
                    "back within one business day to go over their results in detail and answer any "
                    "questions. Thank them for their time and wish them well."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    f"Thank {self.patient_name} for their time. Remind them that if their doctor "
                    "recommended any follow-up visits or additional tests, they can schedule those "
                    "through our patient portal or by calling us back. Wish them well."
                )
            )

    def leave_voicemail(self):
        self.hangup(
            final_instructions=(
                f"Leave a brief, professional voicemail for {self.patient_name} from Riverside "
                "Family Medicine. Let them know we are calling regarding their recent lab work and "
                "ask them to call us back at their earliest convenience. Do not mention specific "
                "test names, results, or any clinical details in the voicemail."
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Outbound call to notify a patient of their lab results."
    )
    parser.add_argument("phone", help="Patient phone number in E.164 format (e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Patient full name")
    parser.add_argument("--patient-id", required=True, help="Practice Fusion FHIR Patient resource ID")
    parser.add_argument(
        "--result-summary",
        required=True,
        help="Brief plain-text description of results for agent reference (e.g. 'CBC and metabolic panel complete, all values within normal range')",
    )
    args = parser.parse_args()

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=LabResultsController(
            patient_name=args.name,
            patient_id=args.patient_id,
            result_summary=args.result_summary,
        ),
    )

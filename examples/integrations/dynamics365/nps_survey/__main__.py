import guava
import os
import logging
import argparse
import requests
from datetime import datetime

logging.basicConfig(level=logging.INFO)

ACCESS_TOKEN = os.environ["DYNAMICS_ACCESS_TOKEN"]
ORG_URL = os.environ["DYNAMICS_ORG_URL"]  # e.g. https://yourorg.crm.dynamics.com

_BASE_HEADERS = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json",
    "OData-MaxVersion": "4.0",
    "OData-Version": "4.0",
    "Accept": "application/json",
}
HEADERS = {**_BASE_HEADERS, "Prefer": "return=representation"}  # for POST/PATCH that return data
GET_HEADERS = _BASE_HEADERS  # for GET requests

API_BASE = f"{ORG_URL}/api/data/v9.2"


def get_case(case_id: str) -> dict | None:
    """Fetches a single incident record by ID. Returns the case or None."""
    resp = requests.get(
        f"{API_BASE}/incidents({case_id})",
        headers=GET_HEADERS,
        params={
            "$select": "title,ticketnumber,statuscode",
        },
        timeout=10,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def add_case_note(incident_id: str, subject: str, note_text: str) -> None:
    """Posts an internal note (annotation) to an incident record."""
    payload = {
        "subject": subject,
        "notetext": note_text,
        "objectid_incident@odata.bind": f"/incidents({incident_id})",
        "objecttypecode": "incident",
    }
    resp = requests.post(f"{API_BASE}/annotations", headers=HEADERS, json=payload, timeout=10)
    resp.raise_for_status()


def log_phone_call(incident_id: str, subject: str, description: str) -> None:
    """Logs a completed outbound phone call activity against an incident."""
    payload = {
        "subject": subject,
        "description": description,
        "directioncode": True,  # outbound
        "regardingobjectid_incident@odata.bind": f"/incidents({incident_id})",
    }
    resp = requests.post(f"{API_BASE}/phonecalls", headers=HEADERS, json=payload, timeout=10)
    resp.raise_for_status()


class NpsSurveyController(guava.CallController):
    def __init__(self, case_id: str, contact_name: str):
        super().__init__()
        self.case_id = case_id
        self.contact_name = contact_name
        self.case_title = "your recently resolved support case"
        self.ticket_number = ""

        # Pre-call: fetch case details to personalize the survey
        try:
            case = get_case(case_id)
            if case:
                if case.get("title"):
                    self.case_title = f"'{case['title']}'"
                self.ticket_number = case.get("ticketnumber", "")
        except Exception as e:
            logging.error("Failed to fetch case %s pre-call: %s", case_id, e)

        self.set_persona(
            organization_name="Pinnacle Solutions",
            agent_name="Morgan",
            agent_purpose=(
                "to collect customer satisfaction feedback on behalf of Pinnacle Solutions "
                "after a support case has been resolved"
            ),
        )

        self.reach_person(
            contact_full_name=self.contact_name,
            on_success=self.begin_survey,
            on_failure=self.recipient_unavailable,
        )

    def begin_survey(self):
        case_ref = self.ticket_number if self.ticket_number else self.case_title

        self.set_task(
            objective=(
                f"Collect NPS feedback from {self.contact_name} regarding their recently "
                f"resolved case {case_ref}. Keep the call brief and friendly."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.contact_name}, this is Morgan calling from Pinnacle Solutions. "
                    f"I'm following up on your recently resolved support case regarding "
                    f"{self.case_title}. I have just a couple of quick questions — "
                    "this will only take about a minute of your time."
                ),
                guava.Field(
                    key="nps_score",
                    field_type="multiple_choice",
                    description=(
                        "Ask: 'On a scale of 0 to 10 — where 0 is not at all likely and 10 is "
                        "extremely likely — how likely are you to recommend Pinnacle Solutions "
                        "to a friend or colleague?' Capture their numeric score."
                    ),
                    choices=["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"],
                    required=True,
                ),
                guava.Field(
                    key="primary_reason",
                    field_type="text",
                    description=(
                        "Ask: 'What is the primary reason for the score you gave?' "
                        "Capture their explanation."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="improvement_suggestion",
                    field_type="text",
                    description=(
                        "Ask: 'Is there anything specific we could do to improve your experience?' "
                        "Capture their suggestion, or skip if they have nothing to add."
                    ),
                    required=False,
                ),
            ],
            on_complete=self.save_results,
        )

    def save_results(self):
        nps_score = self.get_field("nps_score") or "not provided"
        primary_reason = self.get_field("primary_reason") or ""
        improvement = self.get_field("improvement_suggestion") or ""

        logging.info(
            "NPS results for case %s — score: %s", self.case_id, nps_score
        )

        # Categorise the score for the note
        try:
            score_int = int(nps_score)
            if score_int >= 9:
                category = "Promoter"
            elif score_int >= 7:
                category = "Passive"
            else:
                category = "Detractor"
        except ValueError:
            score_int = -1
            category = "Unknown"

        note_lines = [
            f"NPS survey completed — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            f"Customer: {self.contact_name}",
            f"NPS score: {nps_score}/10 ({category})",
        ]
        if primary_reason:
            note_lines.append(f"Primary reason: {primary_reason}")
        if improvement and improvement.strip().lower() not in ("none", "n/a", ""):
            note_lines.append(f"Improvement suggestion: {improvement}")

        note_text = "\n".join(note_lines)

        try:
            add_case_note(self.case_id, "NPS survey — voice call", note_text)
            logging.info("NPS note added to case %s", self.case_id)
        except Exception as e:
            logging.error("Failed to save NPS note to case %s: %s", self.case_id, e)

        try:
            log_phone_call(
                self.case_id,
                subject=f"NPS survey call — {self.contact_name}",
                description=note_text,
            )
            logging.info("Phone call logged for case %s", self.case_id)
        except Exception as e:
            logging.error("Failed to log phone call for case %s: %s", self.case_id, e)

        if score_int >= 0 and score_int <= 6:
            self.hangup(
                final_instructions=(
                    f"Sincerely thank {self.contact_name} for their candid feedback. "
                    "Acknowledge that we did not fully meet their expectations and let them know "
                    "a member of our customer success team will personally follow up to understand "
                    "how we can do better. Apologize and wish them a good day."
                )
            )
        elif score_int >= 7 and score_int <= 8:
            self.hangup(
                final_instructions=(
                    f"Thank {self.contact_name} for their feedback. Let them know we appreciate "
                    "their honest input and will use it to keep improving. Wish them a great day."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    f"Thank {self.contact_name} warmly for their positive feedback and for being "
                    "a valued Pinnacle Solutions customer. Let them know we are glad we could "
                    "help and we are always here if they need anything. Wish them a wonderful day."
                )
            )

    def recipient_unavailable(self):
        logging.info(
            "Unable to reach %s for NPS survey on case %s", self.contact_name, self.case_id
        )
        self.hangup(
            final_instructions=(
                f"Leave a brief, friendly voicemail for {self.contact_name} on behalf of "
                "Pinnacle Solutions. Let them know you were calling to follow up on their "
                f"recently resolved support case regarding {self.case_title}. "
                "Let them know no action is needed and you hope everything is working well. "
                "Wish them a great day."
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Outbound NPS survey call after a Dynamics 365 support case is resolved."
    )
    parser.add_argument(
        "phone", help="Customer phone number to call (E.164 format, e.g. +15551234567)"
    )
    parser.add_argument("--case-id", required=True, help="Dynamics 365 incident (case) ID (GUID)")
    parser.add_argument("--name", required=True, help="Customer's full name")
    args = parser.parse_args()

    logging.info(
        "Initiating NPS survey call to %s (%s) for case %s",
        args.name, args.phone, args.case_id,
    )

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=NpsSurveyController(
            case_id=args.case_id,
            contact_name=args.name,
        ),
    )

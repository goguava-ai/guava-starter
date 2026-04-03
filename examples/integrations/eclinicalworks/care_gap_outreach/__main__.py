import guava
import os
import logging
import argparse
import requests

logging.basicConfig(level=logging.INFO)


def get_access_token() -> str:
    resp = requests.post(
        os.environ["ECW_TOKEN_URL"],
        data={"grant_type": "client_credentials", "scope": "system/*.read system/*.write"},
        auth=(os.environ["ECW_CLIENT_ID"], os.environ["ECW_CLIENT_SECRET"]),
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def post_communication_request(patient_id: str, care_gap: str, intent: str, headers: dict) -> bool:
    base_url = os.environ["ECW_BASE_URL"]
    payload = {
        "resourceType": "CommunicationRequest",
        "status": "active",
        "subject": {"reference": f"Patient/{patient_id}"},
        "reasonCode": [{"text": f"Care gap outreach: {care_gap}"}],
        "note": [{"text": f"Patient scheduling intent: {intent}"}],
    }
    resp = requests.post(f"{base_url}/CommunicationRequest", headers=headers, json=payload, timeout=10)
    return resp.ok


class CareGapOutreachController(guava.CallController):
    def __init__(self, patient_name: str, patient_id: str, care_gap: str):
        super().__init__()
        self.patient_name = patient_name
        self.patient_id = patient_id
        self.care_gap = care_gap
        self.headers = {}

        try:
            token = get_access_token()
            self.headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        except Exception as e:
            logging.error("Token error: %s", e)

        self.set_persona(
            organization_name="Sunrise Family Practice",
            agent_name="Sam",
            agent_purpose=(
                "to reach out to patients who are overdue for preventive care and help them schedule"
            ),
        )

        self.set_task(
            objective=(
                f"Call {patient_name} who is due for a {care_gap}. "
                "Educate them on the importance, address any concerns, and gauge their intent to schedule."
            ),
            checklist=[
                guava.Say(
                    f"Hi {patient_name}, this is Sam calling from Sunrise Family Practice. "
                    f"I'm reaching out because our records show you may be due for a {care_gap}. "
                    "We just wanted to give you a friendly reminder — these visits are an important "
                    "part of staying on top of your health."
                ),
                guava.Field(
                    key="aware",
                    field_type="multiple_choice",
                    description=f"Ask if they were aware they were due for a {care_gap}.",
                    choices=["yes", "no"],
                    required=True,
                ),
                guava.Field(
                    key="barriers",
                    field_type="multiple_choice",
                    description="Ask if there are any barriers preventing them from coming in.",
                    choices=["no barriers", "scheduling difficulty", "cost concerns", "feeling well / no symptoms", "other"],
                    required=True,
                ),
                guava.Field(
                    key="scheduling_intent",
                    field_type="multiple_choice",
                    description="Ask if they'd like to schedule today or have someone follow up.",
                    choices=["yes, schedule now", "follow up later", "not interested"],
                    required=True,
                ),
            ],
            on_complete=self.handle_intent,
        )

        self.reach_person(
            contact_full_name=self.patient_name,
            on_success=lambda: None,
            on_failure=self.leave_voicemail,
        )

    def handle_intent(self):
        intent = self.get_field("scheduling_intent") or ""
        barriers = self.get_field("barriers") or ""

        logging.info(
            "Care gap outreach for patient %s — gap: %s, intent: %s, barriers: %s",
            self.patient_id, self.care_gap, intent, barriers,
        )

        try:
            post_communication_request(self.patient_id, self.care_gap, intent, self.headers)
        except Exception as e:
            logging.error("Failed to post CommunicationRequest: %s", e)

        if "schedule now" in intent:
            self.hangup(
                final_instructions=(
                    f"Let {self.patient_name} know that a scheduling coordinator will call them "
                    "back within one business day to find a time that works. "
                    "Thank them for their commitment to their health and wish them a great day."
                )
            )
        elif "follow up" in intent:
            self.hangup(
                final_instructions=(
                    f"Thank {self.patient_name} for their time. Let them know we'll reach out "
                    "again in the near future to help schedule. They can also call the office anytime. "
                    "Wish them a great day."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    f"Respect {self.patient_name}'s decision. Let them know we're always here "
                    "if they change their mind. Thank them for taking the call and wish them well."
                )
            )

    def leave_voicemail(self):
        logging.info("Unable to reach %s for care gap outreach.", self.patient_name)
        self.hangup(
            final_instructions=(
                f"Leave a brief, warm voicemail for {self.patient_name} from Sunrise Family Practice. "
                f"Let them know you're calling because they may be due for a {self.care_gap} "
                "and invite them to call back to schedule. Keep it friendly and non-alarming."
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Outbound care gap outreach via eClinicalWorks FHIR.")
    parser.add_argument("phone", help="Patient phone number (E.164)")
    parser.add_argument("--name", required=True)
    parser.add_argument("--patient-id", required=True)
    parser.add_argument("--care-gap", required=True, help="Care gap description (e.g. 'annual wellness visit')")
    args = parser.parse_args()

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=CareGapOutreachController(
            patient_name=args.name,
            patient_id=args.patient_id,
            care_gap=args.care_gap,
        ),
    )

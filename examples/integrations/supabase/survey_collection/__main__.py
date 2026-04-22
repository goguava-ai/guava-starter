import guava
import os
import logging
from guava import logging_utils
import requests
from datetime import datetime, timezone


SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
REST_URL = f"{SUPABASE_URL}/rest/v1"


def get_headers() -> dict:
    service_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def insert_survey_response(data: dict) -> dict | None:
    table = os.environ.get("SUPABASE_SURVEY_TABLE", "survey_responses")
    resp = requests.post(
        f"{REST_URL}/{table}",
        headers=get_headers(),
        json=data,
        timeout=10,
    )
    resp.raise_for_status()
    rows = resp.json()
    return rows[0] if rows else None


class SurveyCollectionController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Clearline",
            agent_name="Jamie",
            agent_purpose=(
                "to collect customer satisfaction survey responses on behalf of Clearline"
            ),
        )

        self.set_task(
            objective=(
                "You are conducting a brief customer satisfaction survey for Clearline. "
                "Collect the customer's name, satisfaction rating, what went well, "
                "improvement suggestions, and NPS score, then save to Supabase."
            ),
            checklist=[
                guava.Say(
                    "Hi, this is Jamie from Clearline. "
                    "We'd love your feedback — this will only take about a minute."
                ),
                guava.Field(
                    key="respondent_name",
                    field_type="text",
                    description="Ask for their first and last name.",
                    required=True,
                ),
                guava.Field(
                    key="email",
                    field_type="text",
                    description="Ask for their email address so we can follow up if needed.",
                    required=False,
                ),
                guava.Field(
                    key="satisfaction_score",
                    field_type="multiple_choice",
                    description="Ask them to rate their overall satisfaction on a scale of 1 to 5.",
                    choices=["1", "2", "3", "4", "5"],
                    required=True,
                ),
                guava.Field(
                    key="what_went_well",
                    field_type="text",
                    description="Ask what they appreciated most about their experience.",
                    required=False,
                ),
                guava.Field(
                    key="improvement",
                    field_type="text",
                    description="Ask if there's anything they'd like to see improved.",
                    required=False,
                ),
                guava.Field(
                    key="nps_score",
                    field_type="multiple_choice",
                    description=(
                        "Ask on a scale of 0 to 10, how likely they are to recommend Clearline "
                        "to a friend or colleague."
                    ),
                    choices=["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"],
                    required=True,
                ),
            ],
            on_complete=self.save_response,
        )

        self.accept_call()

    def save_response(self):
        respondent_name = self.get_field("respondent_name") or ""
        email = self.get_field("email") or ""
        satisfaction_score = self.get_field("satisfaction_score") or ""
        what_went_well = self.get_field("what_went_well") or ""
        improvement = self.get_field("improvement") or ""
        nps_score = self.get_field("nps_score") or ""

        data: dict = {
            "respondent_name": respondent_name,
            "channel": "phone",
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        }
        if email:
            data["email"] = email
        if satisfaction_score.isdigit():
            data["satisfaction_score"] = int(satisfaction_score)
        if what_went_well:
            data["what_went_well"] = what_went_well
        if improvement:
            data["improvement_suggestions"] = improvement
        if nps_score.isdigit():
            data["nps_score"] = int(nps_score)

        logging.info("Saving survey response from %s", respondent_name)

        saved = None
        try:
            saved = insert_survey_response(data)
            logging.info("Survey response saved: %s", saved.get("id") if saved else None)
        except Exception as e:
            logging.error("Failed to save survey response: %s", e)

        first_name = respondent_name.split()[0] if respondent_name else "there"

        if saved:
            self.hangup(
                final_instructions=(
                    f"Thank {first_name} sincerely for taking the time to share their feedback. "
                    "Let them know their response has been recorded and will help us improve Clearline. "
                    "Wish them a wonderful day."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    f"Thank {first_name} for their time. "
                    "Apologize that we had a technical issue saving their response "
                    "but genuinely appreciate their feedback. Wish them a great day."
                )
            )


if __name__ == "__main__":
    logging_utils.configure_logging()
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=SurveyCollectionController,
    )

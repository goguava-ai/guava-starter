import guava
import os
import logging
from guava import logging_utils
import requests
from datetime import datetime, timezone
from urllib.parse import quote


BASE_ID = os.environ["AIRTABLE_BASE_ID"]
TABLE_NAME = os.environ.get("AIRTABLE_SURVEY_TABLE", "Survey Responses")
BASE_URL = f"https://api.airtable.com/v0/{BASE_ID}/{quote(TABLE_NAME)}"


def get_headers() -> dict:
    return {
        "Authorization": f"Bearer {os.environ['AIRTABLE_API_KEY']}",
        "Content-Type": "application/json",
    }


def save_response(fields: dict) -> dict | None:
    resp = requests.post(BASE_URL, headers=get_headers(), json={"fields": fields}, timeout=10)
    resp.raise_for_status()
    return resp.json()


agent = guava.Agent(
    name="Alex",
    organization="Meridian Team",
    purpose=(
        "to collect customer satisfaction survey responses on behalf of the Meridian Team"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "save_survey",
        objective=(
            "You are conducting a brief customer satisfaction survey. "
            "Collect the customer's name, overall satisfaction, what they liked, "
            "and any suggestions for improvement, then log it to Airtable."
        ),
        checklist=[
            guava.Say(
                "Hi, this is Alex calling from Meridian Team. "
                "We'd love to get your feedback — this survey will only take about a minute."
            ),
            guava.Field(
                key="respondent_name",
                field_type="text",
                description="Ask for their first and last name.",
                required=True,
            ),
            guava.Field(
                key="overall_rating",
                field_type="multiple_choice",
                description="Ask them to rate their overall experience on a scale of 1 to 5.",
                choices=["1", "2", "3", "4", "5"],
                required=True,
            ),
            guava.Field(
                key="what_went_well",
                field_type="text",
                description="Ask what went well or what they appreciated most.",
                required=False,
            ),
            guava.Field(
                key="improvement_suggestion",
                field_type="text",
                description="Ask if there's anything they'd like to see improved.",
                required=False,
            ),
            guava.Field(
                key="recommend",
                field_type="multiple_choice",
                description="Ask how likely they are to recommend Meridian Team to a colleague.",
                choices=["very likely", "likely", "neutral", "unlikely", "very unlikely"],
                required=True,
            ),
        ],
    )


@agent.on_task_complete("save_survey")
def on_done(call: guava.Call) -> None:
    respondent_name = call.get_field("respondent_name") or ""
    overall_rating = call.get_field("overall_rating") or ""
    what_went_well = call.get_field("what_went_well") or ""
    improvement_suggestion = call.get_field("improvement_suggestion") or ""
    recommend = call.get_field("recommend") or ""

    fields: dict = {
        "Name": respondent_name,
        "Overall Rating": int(overall_rating) if overall_rating.isdigit() else None,
        "What Went Well": what_went_well,
        "Improvement Suggestions": improvement_suggestion,
        "Likelihood to Recommend": recommend,
        "Response Date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "Channel": "Phone",
    }
    fields = {k: v for k, v in fields.items() if v is not None and v != ""}

    logging.info("Saving survey response from %s", respondent_name)

    saved = None
    try:
        saved = save_response(fields)
        logging.info("Survey response saved: %s", saved.get("id") if saved else None)
    except Exception as e:
        logging.error("Failed to save survey response: %s", e)

    if saved:
        call.hangup(
            final_instructions=(
                f"Thank {respondent_name or 'them'} sincerely for taking the time to share their feedback. "
                "Let them know their response has been recorded and will help us improve. "
                "Wish them a great rest of their day."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                "Thank the respondent for their time. Let them know we had a technical issue "
                "saving their responses but we appreciate their feedback. "
                "Apologize for any inconvenience and wish them a great day."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])

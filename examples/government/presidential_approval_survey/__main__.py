# SDK conformance: guava-sdk 0.34.0 (2026-07-14)
import argparse
import json
import logging
import os
from datetime import datetime

import guava
from guava import logging_utils

agent = guava.Agent(
    name="Alex",
    organization="American Public Opinion Research",
    purpose=(
        "You are conducting a brief nonpartisan presidential approval survey "
        "on behalf of American Public Opinion Research, a nonprofit polling organization. "
        "Be neutral, professional, and respectful at all times."
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "survey",
        objective=(
            "Conduct a brief nonpartisan presidential approval phone survey. "
            "Start by introducing yourself and asking if the respondent has about two minutes "
            "to answer a few questions. If they decline, thank them and end the call politely. "
            "Ask each question in a neutral, unbiased manner without editorializing."
        ),
        checklist=[
            "Introduce yourself as Alex from American Public Opinion Research and ask "
            "if the respondent has about two minutes to answer a few survey questions about "
            "the current presidential administration.",
            guava.Field(
                key="presidential_approval",
                description=(
                    "Overall, what do you think of the job the president is currently doing?"
                ),
                field_type="multiple_choice",
                choices=["approve", "disapprove", "no opinion"],
            ),
            guava.Field(
                key="economic_approval",
                description=(
                    "What do you think of the president's handling of the economy?"
                ),
                field_type="multiple_choice",
                choices=["approve", "disapprove", "no opinion"],
            ),
            guava.Field(
                key="foreign_policy_approval",
                description=(
                    "What do you think of the president's handling of foreign policy "
                    "and national security?"
                ),
                field_type="multiple_choice",
                choices=["approve", "disapprove", "no opinion"],
            ),
            guava.Field(
                key="healthcare_approval",
                description=(
                    "What do you think of the president's handling of healthcare policy?"
                ),
                field_type="multiple_choice",
                choices=["approve", "disapprove", "no opinion"],
            ),
            guava.Field(
                key="most_important_issue",
                description=(
                    "In your opinion, what is the single most important issue facing "
                    "the country right now?"
                ),
                field_type="text",
            ),
            guava.Field(
                key="party_affiliation",
                description=(
                    "For demographic purposes, how would you describe your political "
                    "affiliation? You are welcome to decline to answer."
                ),
                field_type="multiple_choice",
                choices=["Democrat", "Republican", "Independent", "something else"],
                required=False,
            ),
            "Thank the respondent sincerely for their time and participation in the survey.",
        ],
    )


@agent.on_task_complete("survey")
def on_done(call: guava.Call) -> None:
    results = {
        "timestamp": datetime.now().isoformat(),
        "presidential_approval": call.get_field("presidential_approval"),
        "economic_approval": call.get_field("economic_approval"),
        "foreign_policy_approval": call.get_field("foreign_policy_approval"),
        "healthcare_approval": call.get_field("healthcare_approval"),
        "most_important_issue": call.get_field("most_important_issue"),
        "party_affiliation": call.get_field("party_affiliation"),
    }
    print("\n=== Survey Results ===")
    print(json.dumps(results, indent=2))
    call.hangup(
        final_instructions="Thank the respondent warmly for their participation and say goodbye."
    )


@agent.on_outbound_failed
def on_outbound_failed(event):
    logging.error("Outbound call failed: %s (code %d)", event.error_reason, event.error_code)


@agent.on_session_end
def on_session_end(call: guava.Call) -> None:
    logging.info("Session ended — collected fields: %s", json.dumps({
        "presidential_approval": call.get_field("presidential_approval"),
        "economic_approval": call.get_field("economic_approval"),
        "foreign_policy_approval": call.get_field("foreign_policy_approval"),
        "healthcare_approval": call.get_field("healthcare_approval"),
        "most_important_issue": call.get_field("most_important_issue"),
        "party_affiliation": call.get_field("party_affiliation"),
    }, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Nonpartisan presidential approval survey call."
    )
    parser.add_argument("phone", help="Respondent phone number to call")
    parser.add_argument(
        "--from-number",
        default=os.environ.get("GUAVA_AGENT_NUMBER", ""),
        help="Caller ID / from number (defaults to GUAVA_AGENT_NUMBER env var).",
    )
    args = parser.parse_args()

    agent.call_phone(
        from_number=args.from_number,
        to_number=args.phone,
    )

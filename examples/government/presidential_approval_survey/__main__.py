# SDK conformance: guava-sdk 0.35.0 (2026-07-21)
import argparse
import json
import logging
import os
from datetime import datetime, timezone

import guava
from guava import logging_utils
from guava.helpers.llm import IntentRecognizer
from guava.events import BotSessionEnded, OutboundCallFailed

agent = guava.Agent(
    name="Sage",
    organization="American Public Opinion Research",
    purpose=(
        "conduct a brief nonpartisan presidential approval survey, ask "
        "follow-up probes based on responses, and record structured results"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
})


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(
        contact_full_name=call.get_variable("respondent_name"),
        voicemail_message=(
            f"Hi, this is Sage from American Public Opinion Research calling for "
            f"{call.get_variable('respondent_name')}. We are conducting a brief, "
            f"voluntary presidential approval survey. Please call us back at your "
            f"convenience if you would like to participate. Thank you."
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    respondent_name = call.get_variable("respondent_name")

    if outcome == "available":
        call.set_task(
            "survey",
            objective=(
                f"Conduct a brief nonpartisan presidential approval phone survey "
                f"with {respondent_name}. Start by asking if they have about two "
                f"minutes. If they decline, thank them and wish them well. "
                f"Ask each question in a neutral, unbiased manner without "
                f"editorializing."
            ),
            checklist=[
                guava.Say(
                    "We're a nonprofit polling organization conducting a brief, "
                    "nonpartisan presidential approval survey. Do you have about "
                    "two minutes to answer a few questions?"
                ),
                guava.Field(
                    key="presidential_approval",
                    description=(
                        "Overall, what do you think of the job the president is "
                        "currently doing?"
                    ),
                    field_type="multiple_choice",
                    choices=["approve", "disapprove", "no opinion"],
                    required=True,
                ),
                guava.Field(
                    key="economic_approval",
                    description=(
                        "What do you think of the president's handling of the economy?"
                    ),
                    field_type="multiple_choice",
                    choices=["approve", "disapprove", "no opinion"],
                    required=True,
                ),
                guava.Field(
                    key="foreign_policy_approval",
                    description=(
                        "What do you think of the president's handling of foreign "
                        "policy and national security?"
                    ),
                    field_type="multiple_choice",
                    choices=["approve", "disapprove", "no opinion"],
                    required=True,
                ),
                guava.Field(
                    key="healthcare_approval",
                    description=(
                        "What do you think of the president's handling of healthcare "
                        "policy?"
                    ),
                    field_type="multiple_choice",
                    choices=["approve", "disapprove", "no opinion"],
                    required=True,
                ),
                guava.Field(
                    key="most_important_issue",
                    description=(
                        "In your opinion, what is the single most important issue "
                        "facing the country right now?"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="party_affiliation",
                    description=(
                        "For demographic purposes, how would you describe your "
                        "political affiliation? You are welcome to decline to answer."
                    ),
                    field_type="multiple_choice",
                    choices=["Democrat", "Republican", "Independent", "something else"],
                    required=False,
                ),
            ],
        )
    elif outcome == "do_not_contact":
        logging.info("Respondent %s requested no further contact.", respondent_name)
        call.hangup(
            final_instructions=(
                "Acknowledge their request. Let them know they will not be "
                "contacted again. Thank them and wish them well, and politely say goodbye."
            )
        )
    elif outcome == "wrong_number":
        logging.info("Wrong number reached for %s.", respondent_name)
        call.hangup(final_instructions="Apologize for the mistake and wish them well, and politely say goodbye.")
    else:
        logging.info("Could not reach %s (outcome: %s).", respondent_name, outcome)
        call.hangup()


@agent.on_task_complete("survey")
def on_survey_done(call: guava.Call) -> None:
    approval = call.get_field("presidential_approval")
    respondent_name = call.get_variable("respondent_name")

    if approval == "disapprove":
        call.set_task(
            "disapproval_followup",
            objective=(
                f"{respondent_name} expressed disapproval of the president's "
                f"performance. Ask one or two neutral follow-up questions to "
                f"understand which specific issues drive their disapproval. "
                f"Remain nonpartisan and do not challenge their views."
            ),
            checklist=[
                guava.Field(
                    key="disapproval_primary_reason",
                    description=(
                        "What is the primary issue or reason behind your disapproval "
                        "of the president's performance?"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="direction_of_country",
                    description=(
                        "Do you feel the country is heading in the right direction "
                        "or the wrong direction?"
                    ),
                    field_type="multiple_choice",
                    choices=["right direction", "wrong direction", "not sure"],
                    required=True,
                ),
            ],
        )
    elif approval == "approve":
        call.set_task(
            "approval_followup",
            objective=(
                f"{respondent_name} expressed approval of the president's "
                f"performance. Ask one or two neutral follow-up questions to "
                f"understand which specific issues drive their approval. "
                f"Remain nonpartisan and do not challenge their views."
            ),
            checklist=[
                guava.Field(
                    key="approval_primary_reason",
                    description=(
                        "What is the primary issue or reason behind your approval "
                        "of the president's performance?"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="direction_of_country",
                    description=(
                        "Do you feel the country is heading in the right direction "
                        "or the wrong direction?"
                    ),
                    field_type="multiple_choice",
                    choices=["right direction", "wrong direction", "not sure"],
                    required=True,
                ),
            ],
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {respondent_name} sincerely for their time and "
                f"participation in the survey, and wish them a good day, and politely say goodbye."
            )
        )


@agent.on_task_complete("disapproval_followup")
def on_disapproval_done(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            f"Thank {call.get_variable('respondent_name')} warmly for sharing "
            f"their perspective and for participating in the survey. Wish them "
            f"a good day, and politely say goodbye."
        )
    )


@agent.on_task_complete("approval_followup")
def on_approval_done(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            f"Thank {call.get_variable('respondent_name')} warmly for sharing "
            f"their perspective and for participating in the survey. Wish them "
            f"a good day, and politely say goodbye."
        )
    )


@agent.on_action_request
def on_action_request(call: guava.Call, intent_summary: str):
    return _mid_call_intent.classify(intent_summary)


@agent.on_action("do_not_contact")
def handle_dnc(call: guava.Call) -> None:
    logging.info("Respondent %s requested DNC mid-call.", call.get_variable("respondent_name"))
    call.hangup(
        final_instructions=(
            "Acknowledge their request. Let them know they will not be contacted "
            "again. Thank them and wish them well, and politely say goodbye."
        )
    )


@agent.on_outbound_failed
def on_outbound_failed(event: OutboundCallFailed) -> None:
    logging.error("Outbound call failed: %s (code %d)", event.error_reason, event.error_code)


@agent.on_session_end
def on_session_end(call: guava.Call, event: BotSessionEnded) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "use_case": "presidential_approval_survey",
        "respondent_name": call.get_variable("respondent_name"),
        "presidential_approval": call.get_field("presidential_approval"),
        "economic_approval": call.get_field("economic_approval"),
        "foreign_policy_approval": call.get_field("foreign_policy_approval"),
        "healthcare_approval": call.get_field("healthcare_approval"),
        "most_important_issue": call.get_field("most_important_issue"),
        "party_affiliation": call.get_field("party_affiliation"),
        "approval_primary_reason": call.get_field("approval_primary_reason"),
        "disapproval_primary_reason": call.get_field("disapproval_primary_reason"),
        "direction_of_country": call.get_field("direction_of_country"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Nonpartisan presidential approval survey call."
    )
    parser.add_argument("phone", help="Respondent phone number to call")
    parser.add_argument("--name", required=True, help="Full name of the respondent.")
    parser.add_argument(
        "--from-number",
        default=os.environ.get("GUAVA_AGENT_NUMBER", ""),
        help="Caller ID / from number (defaults to GUAVA_AGENT_NUMBER env var).",
    )
    args = parser.parse_args()

    agent.call_phone(
        from_number=args.from_number,
        to_number=args.phone,
        variables={
            "respondent_name": args.name,
        },
    )

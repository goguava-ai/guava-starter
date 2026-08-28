# SDK conformance: guava-sdk 0.40.0 (2026-08-26)
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
    name="Quinn",
    organization="Metro Power & Light",
    purpose=(
        "conduct a brief post-interaction satisfaction survey, collect NPS "
        "data, and follow up on low satisfaction scores to understand areas "
        "for improvement"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
    "speak_to_someone": "The caller wants to speak to a manager, supervisor, or customer service representative",
})


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(
        contact_full_name=call.get_variable("contact_name"),
        voicemail_message=(
            f"Hi, this is Quinn from Metro Power & Light calling for "
            f"{call.get_variable('contact_name')}. We're following up on your "
            f"recent experience with us and would love your feedback. Please "
            f"call us back at your convenience. Thank you."
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    contact_name = call.get_variable("contact_name")
    account_number = call.get_variable("account_number")
    interaction_type = call.get_variable("interaction_type")
    interaction_date = call.get_variable("interaction_date")

    if outcome == "available":
        call.set_task(
            "satisfaction_survey",
            objective=(
                f"Conduct a post-interaction satisfaction survey with "
                f"{contact_name} (account {account_number}) regarding "
                f"{interaction_type} on {interaction_date}. Collect NPS score, "
                f"satisfaction rating, resolution status, and any improvement "
                f"suggestions. Keep the survey conversational and brief."
            ),
            checklist=[
                guava.Say(
                    f"I'm following up on {interaction_type} on "
                    f"{interaction_date}. We'd love to get your feedback — this "
                    f"survey takes about two minutes. Do you have a moment?"
                ),
                guava.Field(
                    key="nps_score",
                    description=(
                        "On a scale of 0 to 10, where 0 is not at all likely and "
                        "10 is extremely likely, how likely are you to recommend "
                        "Metro Power & Light to a friend or family member?"
                    ),
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="interaction_satisfaction_rating",
                    description=(
                        "On a scale of 1 to 5, where 1 is very dissatisfied and "
                        "5 is very satisfied, how satisfied were you with your "
                        "overall experience during this interaction?"
                    ),
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="issue_resolved",
                    description=(
                        "Whether the customer's issue or request was fully resolved "
                        "during their interaction"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="wait_time_acceptable",
                    description=(
                        "Whether the customer found the wait time to reach a "
                        "representative acceptable"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="agent_helpfulness_rating",
                    description=(
                        "On a scale of 1 to 5, where 1 is not helpful at all and "
                        "5 is extremely helpful, how would you rate the helpfulness "
                        "of the representative you spoke with?"
                    ),
                    field_type="integer",
                    required=True,
                ),
            ],
        )
    elif outcome == "do_not_contact":
        logging.info("Customer %s requested no further contact.", contact_name)
        call.hangup(
            final_instructions=(
                "Acknowledge their request. Let them know they will not be "
                "contacted again by phone for surveys. Thank them, and politely say goodbye."
            )
        )
    elif outcome == "wrong_number":
        logging.info("Wrong number reached for %s.", contact_name)
        call.hangup(final_instructions="Apologize for the mistake and wish them well, and politely say goodbye.")
    else:
        logging.info("Could not reach %s (outcome: %s).", contact_name, outcome)
        call.hangup()


@agent.on_task_complete("satisfaction_survey")
def on_survey_done(call: guava.Call) -> None:
    satisfaction = call.get_field("interaction_satisfaction_rating")
    contact_name = call.get_variable("contact_name")

    if satisfaction is not None and satisfaction <= 2:
        call.set_task(
            "low_satisfaction_followup",
            objective=(
                f"{contact_name} gave a low satisfaction rating ({satisfaction}/5). "
                f"Ask what specifically went wrong and what Metro Power & Light "
                f"could have done better. Listen carefully and be empathetic. "
                f"Let them know their feedback will be escalated for review."
            ),
            checklist=[
                guava.Field(
                    key="dissatisfaction_reason",
                    description="What specifically the customer was unhappy about",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="improvement_suggestions",
                    description=(
                        "Any suggestions for how Metro Power & Light could "
                        "improve its service"
                    ),
                    field_type="text",
                    required=False,
                ),
            ],
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {contact_name} sincerely for taking the time to complete "
                f"the survey. Let them know their feedback is reviewed by the Metro "
                f"Power & Light team, and wish them a good day, and politely say goodbye."
            )
        )


@agent.on_task_complete("low_satisfaction_followup")
def on_low_satisfaction_done(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            f"Thank {call.get_variable('contact_name')} for sharing their "
            f"feedback — it genuinely helps. Apologize for their experience "
            f"falling short of expectations. Let them know their feedback will "
            f"be escalated and reviewed, and wish them a good day, and politely say goodbye."
        )
    )


@agent.on_action_request
def on_action_request(call: guava.Call, intent_summary: str):
    return _mid_call_intent.classify(intent_summary)


@agent.on_action("do_not_contact")
def handle_dnc(call: guava.Call) -> None:
    logging.info("Customer %s requested DNC mid-call.", call.get_variable("contact_name"))
    call.hangup(
        final_instructions=(
            "Acknowledge their request. Let them know they will not be contacted "
            "again by phone, and wish them well, and politely say goodbye."
        )
    )


@agent.on_action("speak_to_someone")
def handle_speak_to_someone(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            "Let them know that a Metro Power & Light manager will review their "
            "feedback and call them back within one business day. Ask if there's "
            "a preferred time and thank them, and politely say goodbye."
        )
    )


@agent.on_outbound_failed
def on_outbound_failed(event: OutboundCallFailed) -> None:
    logging.error("Outbound call failed: %s (code %d)", event.error_reason, event.error_code)


@agent.on_session_end
def on_session_end(call: guava.Call, event: BotSessionEnded) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "use_case": "satisfaction_survey",
        "contact_name": call.get_variable("contact_name"),
        "account_number": call.get_variable("account_number"),
        "interaction_type": call.get_variable("interaction_type"),
        "interaction_date": call.get_variable("interaction_date"),
        "nps_score": call.get_field("nps_score"),
        "interaction_satisfaction_rating": call.get_field("interaction_satisfaction_rating"),
        "issue_resolved": call.get_field("issue_resolved"),
        "wait_time_acceptable": call.get_field("wait_time_acceptable"),
        "agent_helpfulness_rating": call.get_field("agent_helpfulness_rating"),
        "dissatisfaction_reason": call.get_field("dissatisfaction_reason"),
        "improvement_suggestions": call.get_field("improvement_suggestions"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Metro Power & Light — Post-Interaction Satisfaction Survey"
    )
    parser.add_argument("phone", help="Customer phone number to call")
    parser.add_argument("--name", required=True, help="Customer full name")
    parser.add_argument("--account-number", required=True, help="Customer account number")
    parser.add_argument(
        "--interaction-type",
        required=True,
        help="Description of the interaction being surveyed (e.g. 'your recent call with us')",
    )
    parser.add_argument(
        "--interaction-date",
        required=True,
        help="Date of the interaction being surveyed (e.g. 'February 20th')",
    )
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
            "contact_name": args.name,
            "account_number": args.account_number,
            "interaction_type": args.interaction_type,
            "interaction_date": args.interaction_date,
        },
    )

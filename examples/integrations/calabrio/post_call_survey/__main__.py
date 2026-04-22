import argparse
import json
import logging
import os
from datetime import datetime, timezone

import guava
import requests
from guava import logging_utils

CALABRIO_BASE_URL = os.environ["CALABRIO_BASE_URL"]
CALABRIO_API_KEY = os.environ["CALABRIO_API_KEY"]

HEADERS = {
    "apiKey": CALABRIO_API_KEY,
    "Content-Type": "application/json",
    "Accept": "application/json",
}


def submit_survey_response(
    interaction_id: str,
    customer_name: str,
    overall_satisfaction: int,
    agent_score: int,
    resolution_confirmed: bool,
    verbatim: str,
    would_recommend: bool,
) -> dict:
    """Submits a post-call customer satisfaction survey to Calabrio."""
    payload = {
        "interactionId": interaction_id,
        "surveyType": "PostCallCSAT",
        "respondentName": customer_name,
        "submittedAt": datetime.now(timezone.utc).isoformat(),
        "responses": {
            "overallSatisfaction": overall_satisfaction,
            "agentPerformance": agent_score,
            "issueResolved": resolution_confirmed,
            "nps": 10 if would_recommend else 5,
            "verbatimFeedback": verbatim,
        },
    }
    resp = requests.post(
        f"{CALABRIO_BASE_URL}/api/surveys/responses",
        headers=HEADERS,
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


agent = guava.Agent(
    name="Alex",
    organization="Horizon Contact Center",
    purpose=(
        "to collect brief feedback about a customer's recent experience with "
        "Horizon Contact Center"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(contact_full_name=call.get_variable("customer_name"))


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    if outcome == "unavailable":
        customer_name = call.get_variable("customer_name")
        interaction_id = call.get_variable("interaction_id")
        logging.info(
            "Unable to reach %s for post-call survey (interaction %s)",
            customer_name, interaction_id,
        )
        call.hangup(
            final_instructions=(
                f"Leave a brief voicemail for {customer_name} from Horizon Contact "
                "Center. Let them know you were following up about their recent call and "
                "wanted to get quick feedback. Mention they can share feedback through "
                "our website as well. Thank them for their time."
            )
        )
    elif outcome == "available":
        customer_name = call.get_variable("customer_name")
        agent_name = call.get_variable("agent_name")
        first_name = customer_name.split()[0] if customer_name else "there"

        call.set_task(
            "post_call_survey",
            objective=(
                f"Conduct a brief post-call satisfaction survey with {customer_name} "
                f"about their recent interaction with agent {agent_name}."
            ),
            checklist=[
                guava.Say(
                    f"Hi {first_name}, this is Alex calling from Horizon Contact Center. "
                    "You recently spoke with one of our agents and we'd love to get your "
                    "feedback. This will only take about 60 seconds — is now a good time?"
                ),
                guava.Field(
                    key="willing_to_participate",
                    field_type="multiple_choice",
                    description="Confirm they are willing to take the brief survey.",
                    choices=["yes", "no"],
                    required=True,
                ),
                guava.Field(
                    key="overall_satisfaction",
                    field_type="multiple_choice",
                    description=(
                        "Ask: 'On a scale of 1 to 5, how satisfied were you with your "
                        "overall experience — 1 being very dissatisfied and 5 being very satisfied?'"
                    ),
                    choices=["1", "2", "3", "4", "5"],
                    required=True,
                ),
                guava.Field(
                    key="agent_score",
                    field_type="multiple_choice",
                    description=(
                        "Ask: 'How would you rate the agent who helped you — 1 to 5?'"
                    ),
                    choices=["1", "2", "3", "4", "5"],
                    required=True,
                ),
                guava.Field(
                    key="issue_resolved",
                    field_type="multiple_choice",
                    description=(
                        "Ask: 'Was your issue fully resolved during the call?'"
                    ),
                    choices=["yes", "partially", "no"],
                    required=True,
                ),
                guava.Field(
                    key="would_recommend",
                    field_type="multiple_choice",
                    description=(
                        "Ask: 'Would you recommend Horizon Contact Center to a friend or colleague?'"
                    ),
                    choices=["yes", "no", "not sure"],
                    required=True,
                ),
                guava.Field(
                    key="verbatim_feedback",
                    field_type="text",
                    description=(
                        "Ask: 'Is there anything else you'd like to share about your experience?' "
                        "Capture their feedback. Optional."
                    ),
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("post_call_survey")
def on_done(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    interaction_id = call.get_variable("interaction_id")
    willing = call.get_field("willing_to_participate")

    if willing == "no":
        logging.info("Customer %s declined survey", customer_name)
        call.hangup(
            final_instructions=(
                "Thank them for their time and let them know their feedback is always "
                "welcome. Wish them a great day."
            )
        )
        return

    overall = call.get_field("overall_satisfaction") or "3"
    agent_score = call.get_field("agent_score") or "3"
    issue_resolved_raw = call.get_field("issue_resolved")
    recommend_raw = call.get_field("would_recommend")
    verbatim = call.get_field("verbatim_feedback") or ""

    resolution_confirmed = issue_resolved_raw == "yes"
    would_recommend = recommend_raw == "yes"

    logging.info(
        "Survey complete for interaction %s — satisfaction: %s, agent: %s, resolved: %s",
        interaction_id, overall, agent_score, issue_resolved_raw,
    )

    try:
        result = submit_survey_response(
            interaction_id=interaction_id,
            customer_name=customer_name,
            overall_satisfaction=int(overall),
            agent_score=int(agent_score),
            resolution_confirmed=resolution_confirmed,
            verbatim=verbatim,
            would_recommend=would_recommend,
        )
        survey_id = result.get("id") or result.get("surveyResponseId", "")
        logging.info("Survey response recorded: %s", survey_id)

        outcome = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": "Alex",
            "use_case": "post_call_survey",
            "customer_name": customer_name,
            "interaction_id": interaction_id,
            "survey_response_id": str(survey_id),
            "overall_satisfaction": overall,
            "agent_score": agent_score,
            "issue_resolved": issue_resolved_raw,
            "would_recommend": recommend_raw,
            "verbatim": verbatim,
        }
        print(json.dumps(outcome, indent=2))
    except Exception as e:
        logging.error("Failed to submit survey response: %s", e)

    first_name = customer_name.split()[0] if customer_name else "there"
    overall_int = int(overall)

    if overall_int >= 4:
        call.hangup(
            final_instructions=(
                f"Thank {first_name} genuinely for their time and positive feedback. "
                "Let them know their input helps us continue to improve. "
                "Wish them a wonderful day."
            )
        )
    elif not resolution_confirmed or overall_int <= 2:
        call.hangup(
            final_instructions=(
                f"Thank {first_name} for their honest feedback and sincerely apologize "
                "for any disappointment with the experience. Let them know their feedback "
                "will be reviewed by our team and that a supervisor may follow up if "
                "their issue was unresolved. Wish them a great day."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {first_name} for their feedback. Let them know we appreciate "
                "them taking the time and that their input helps us improve. Wish them a great day."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound post-call CSAT survey using Calabrio interaction data."
    )
    parser.add_argument("phone", help="Customer phone number (E.164, e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Customer full name")
    parser.add_argument("--interaction-id", required=True, help="Calabrio interaction/contact ID")
    parser.add_argument("--agent-name", required=True, help="Name of the agent who handled the call")
    args = parser.parse_args()

    logging.info(
        "Initiating post-call survey for %s (interaction %s)",
        args.name, args.interaction_id,
    )

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "customer_name": args.name,
            "interaction_id": args.interaction_id,
            "agent_name": args.agent_name,
        },
    )

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
    name="Sam",
    organization="National Internet Wealth Management",
    purpose=(
        "conduct a brief client satisfaction survey covering advisor performance, "
        "portfolio satisfaction, and overall service quality, with follow-up "
        "questions tailored to the client's risk tolerance"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
    "speak_to_someone": "The caller wants to speak to their advisor or a live person",
})


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(
        contact_full_name=call.get_variable("contact_name"),
        voicemail_message=(
            f"Hi, this is Sam from National Internet Wealth Management calling for "
            f"{call.get_variable('contact_name')}. We're reaching out to gather a "
            f"few minutes of feedback about your experience with us. Please call us "
            f"back at 1-800-555-0170 at your convenience. Thank you!"
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    contact_name = call.get_variable("contact_name")
    advisor = call.get_variable("advisor")

    if outcome == "available":
        call.set_task(
            "survey",
            objective=(
                f"Conduct a client satisfaction survey with {contact_name}, a client "
                f"of {advisor}. Gather structured feedback on advisor performance, "
                f"portfolio satisfaction, risk tolerance, and service quality. Keep "
                f"the tone warm, respectful, and efficient. This survey should take "
                f"no more than 5 minutes."
            ),
            checklist=[
                guava.Say(
                    "I'm reaching out to gather a few minutes of feedback about your "
                    "experience with us. Everything you share is confidential. Do you "
                    "have about 5 minutes?"
                ),
                guava.Field(
                    key="advisor_rating",
                    description=(
                        f"Ask the client to rate their overall satisfaction with "
                        f"{advisor} on a scale of 1 to 5, where 1 is very dissatisfied "
                        f"and 5 is very satisfied"
                    ),
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="portfolio_satisfaction",
                    description=(
                        "How satisfied they are with the performance and composition "
                        "of their investment portfolio, including any comments about "
                        "returns, risk level, or asset allocation"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="risk_tolerance",
                    description=(
                        "The client's self-described investment risk tolerance"
                    ),
                    field_type="multiple_choice",
                    choices=["conservative", "moderate", "aggressive"],
                    required=True,
                ),
                guava.Field(
                    key="service_quality_rating",
                    description=(
                        "Rate the overall quality of service from National Internet "
                        "Wealth Management on a scale of 1 to 5"
                    ),
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="likelihood_to_recommend",
                    description=(
                        "How likely they are to recommend National Internet Wealth "
                        "Management on a scale of 0 to 10"
                    ),
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="improvement_suggestions",
                    description=(
                        "Any specific improvements they would suggest — communication "
                        "frequency, reporting, product offerings, or digital tools"
                    ),
                    field_type="text",
                    required=False,
                ),
            ],
        )
    elif outcome == "do_not_contact":
        logging.info("Client %s requested no further contact.", contact_name)
        call.hangup(
            final_instructions=(
                "Acknowledge their request. Let them know they will not be contacted "
                "again for surveys and that their preference has been noted, and politely say goodbye."
            )
        )
    elif outcome == "wrong_number":
        logging.info("Wrong number for %s.", contact_name)
        call.hangup(final_instructions="Apologize for the mistake and wish them well, and politely say goodbye.")
    else:
        logging.info("Could not reach %s (outcome: %s).", contact_name, outcome)
        call.hangup()


@agent.on_task_complete("survey")
def on_survey_done(call: guava.Call) -> None:
    risk_tolerance = call.get_field("risk_tolerance")
    contact_name = call.get_variable("contact_name")
    advisor = call.get_variable("advisor")

    if risk_tolerance == "conservative":
        call.set_task(
            "conservative_followup",
            objective=(
                f"{contact_name} described themselves as a conservative investor. "
                f"Ask about their investment timeline and whether they are primarily "
                f"focused on capital preservation or income generation. This helps "
                f"{advisor} tailor future recommendations."
            ),
            checklist=[
                guava.Field(
                    key="investment_timeline",
                    description=(
                        "The client's investment timeline — for example, short-term "
                        "(1-3 years), medium-term (3-10 years), or long-term (10+ years)"
                    ),
                    field_type="multiple_choice",
                    choices=["short_term", "medium_term", "long_term"],
                    required=True,
                ),
                guava.Field(
                    key="primary_goal",
                    description=(
                        "Whether the client's primary investment goal is capital "
                        "preservation, income generation, or a balance of both"
                    ),
                    field_type="multiple_choice",
                    choices=["capital_preservation", "income_generation", "balanced"],
                    required=True,
                ),
            ],
        )
    elif risk_tolerance == "aggressive":
        call.set_task(
            "aggressive_followup",
            objective=(
                f"{contact_name} described themselves as an aggressive investor. "
                f"Ask about their experience level with high-risk investments and "
                f"whether they are comfortable with significant short-term volatility. "
                f"This helps {advisor} assess suitability."
            ),
            checklist=[
                guava.Field(
                    key="investment_experience",
                    description=(
                        "The client's experience level with high-risk or alternative "
                        "investments such as individual stocks, options, or crypto"
                    ),
                    field_type="multiple_choice",
                    choices=["beginner", "intermediate", "experienced"],
                    required=True,
                ),
                guava.Field(
                    key="volatility_comfort",
                    description=(
                        "Whether the client is comfortable seeing significant "
                        "short-term losses in exchange for potential long-term gains"
                    ),
                    field_type="multiple_choice",
                    choices=["yes", "somewhat", "no"],
                    required=True,
                ),
            ],
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {contact_name} sincerely for completing the survey. Let them "
                f"know their feedback is genuinely valued. Remind them that {advisor} "
                f"is always available if they have questions about their portfolio. "
                f"Wish them a great day, and politely say goodbye."
            )
        )


@agent.on_task_complete("conservative_followup")
def on_conservative_done(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    advisor = call.get_variable("advisor")
    call.hangup(
        final_instructions=(
            f"Thank {contact_name} for sharing those additional insights. Let them "
            f"know {advisor} will use this information to ensure their portfolio "
            f"remains aligned with their goals, and wish them a great day, and politely say goodbye."
        )
    )


@agent.on_task_complete("aggressive_followup")
def on_aggressive_done(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    advisor = call.get_variable("advisor")
    call.hangup(
        final_instructions=(
            f"Thank {contact_name} for sharing those details. Let them know {advisor} "
            f"will review this to ensure their investment strategy matches their "
            f"experience and comfort level, and wish them a great day, and politely say goodbye."
        )
    )


@agent.on_action_request
def on_action_request(call: guava.Call, intent_summary: str):
    return _mid_call_intent.classify(intent_summary)


@agent.on_action("do_not_contact")
def handle_dnc(call: guava.Call) -> None:
    logging.info("Client %s requested DNC mid-call.", call.get_variable("contact_name"))
    call.hangup(
        final_instructions=(
            "Acknowledge their request. Let them know they have been removed from "
            "the survey contact list and will not be called again, and wish them well, and politely say goodbye."
        )
    )


@agent.on_action("speak_to_someone")
def handle_speak_to_someone(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            f"Let them know that {call.get_variable('advisor')} will call them back "
            f"within one business day. Ask if there's a preferred time and thank "
            f"them for their patience, and politely say goodbye."
        )
    )


@agent.on_outbound_failed
def on_outbound_failed(event: OutboundCallFailed) -> None:
    logging.error("Outbound call failed: %s (code %d)", event.error_reason, event.error_code)


@agent.on_session_end
def on_session_end(call: guava.Call, event: BotSessionEnded) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "use_case": "investment_survey",
        "contact_name": call.get_variable("contact_name"),
        "advisor": call.get_variable("advisor"),
        "advisor_rating": call.get_field("advisor_rating"),
        "portfolio_satisfaction": call.get_field("portfolio_satisfaction"),
        "risk_tolerance": call.get_field("risk_tolerance"),
        "service_quality_rating": call.get_field("service_quality_rating"),
        "likelihood_to_recommend": call.get_field("likelihood_to_recommend"),
        "improvement_suggestions": call.get_field("improvement_suggestions"),
        "investment_timeline": call.get_field("investment_timeline"),
        "primary_goal": call.get_field("primary_goal"),
        "investment_experience": call.get_field("investment_experience"),
        "volatility_comfort": call.get_field("volatility_comfort"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound client satisfaction survey for National Internet Wealth Management"
    )
    parser.add_argument("phone", help="Phone number to dial")
    parser.add_argument("--name", required=True, help="Full name of the client")
    parser.add_argument(
        "--advisor",
        default="your advisor",
        help="Full name of the client's assigned advisor (default: 'your advisor')",
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
            "advisor": args.advisor,
        },
    )

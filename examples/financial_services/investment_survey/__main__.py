import argparse
import json
import os
from datetime import datetime, timezone

import guava
from guava import logging_utils

agent = guava.Agent(
    name="Sam",
    organization="First National Wealth Management",
    purpose=(
        "to conduct a brief client satisfaction survey covering advisor performance, "
        "portfolio satisfaction, and overall service quality"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(contact_full_name=call.get_variable("contact_name"))


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    if outcome == "unavailable":
        call.hangup(
            final_instructions=(
                f"You were unable to reach {call.get_variable('contact_name')}. Leave a brief, friendly voicemail "
                f"identifying yourself as Sam from First National Wealth Management. Let them know "
                f"you were calling to gather a few minutes of feedback about their experience with "
                f"us, and that their input is very important to us. Ask them to call back at their "
                f"convenience or mention that you may follow up at another time."
            )
        )
    elif outcome == "available":
        call.set_task(
            "survey",
            objective=(
                f"You are conducting a client satisfaction survey on behalf of First National "
                f"Wealth Management. You are speaking with {call.get_variable('contact_name')}, a client of "
                f"{call.get_variable('advisor')}. The survey is designed to gather structured feedback on advisor "
                f"performance, portfolio satisfaction, and service quality for CRM and compliance "
                f"reporting. Keep the tone warm, respectful, and efficient. This survey should "
                f"take no more than 5 minutes. Thank the client for their time at each step and "
                f"reassure them that their feedback is confidential and will be used to improve "
                f"their experience."
            ),
            checklist=[
                guava.Say(
                    f"Hello {call.get_variable('contact_name')}, this is Sam calling from First National Wealth "
                    f"Management. I am reaching out today to gather a few minutes of feedback about "
                    f"your experience with us. Your responses help us ensure we are delivering the "
                    f"best possible service. Everything you share is confidential. Do you have about "
                    f"5 minutes?"
                ),
                guava.Say(
                    f"Great, let's get started. The first question is about your advisor, "
                    f"{call.get_variable('advisor')}."
                ),
                guava.Field(
                    key="advisor_rating",
                    description=(
                        f"Ask the client to rate their overall satisfaction with {call.get_variable('advisor')} "
                        f"on a scale of 1 to 5, where 1 is very dissatisfied and 5 is very "
                        f"satisfied. Record the numeric rating they provide."
                    ),
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="portfolio_satisfaction",
                    description=(
                        "Ask the client how satisfied they are with the performance and composition "
                        "of their investment portfolio. Invite them to share any specific comments "
                        "about returns, risk level, or asset allocation. Record a summary of their "
                        "response."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Say(
                    "Now I have a couple of quick rating questions. These are on a numeric scale "
                    "and will only take a moment."
                ),
                guava.Field(
                    key="service_quality_rating",
                    description=(
                        "Ask the client to rate the overall quality of service they have received "
                        "from First National Wealth Management — including communication, "
                        "responsiveness, and ease of doing business — on a scale of 1 to 5, where "
                        "1 is very poor and 5 is excellent. Record the numeric rating."
                    ),
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="likelihood_to_recommend",
                    description=(
                        "Ask the client how likely they are to recommend First National Wealth "
                        "Management to a friend or family member on a scale of 0 to 10, where 0 "
                        "is not at all likely and 10 is extremely likely. Record the numeric rating."
                    ),
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="improvement_suggestions",
                    description=(
                        "Ask the client if there is anything specific they feel could be improved "
                        "about their experience — such as communication frequency, reporting, "
                        "product offerings, or digital tools. Record a summary of any suggestions "
                        "they offer. Leave blank if they have no suggestions."
                    ),
                    field_type="text",
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("survey")
def on_done(call: guava.Call) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "contact_name": call.get_variable("contact_name"),
        "advisor": call.get_variable("advisor"),
        "advisor_rating": call.get_field("advisor_rating"),
        "portfolio_satisfaction": call.get_field("portfolio_satisfaction"),
        "service_quality_rating": call.get_field("service_quality_rating"),
        "likelihood_to_recommend": call.get_field("likelihood_to_recommend"),
        "improvement_suggestions": call.get_field("improvement_suggestions"),
    }
    print(json.dumps(results, indent=2))
    call.hangup(
        final_instructions=(
            f"Thank {call.get_variable('contact_name')} sincerely for taking the time to complete the survey. "
            f"Let them know their feedback is genuinely valued and will be reviewed by the "
            f"leadership team at First National Wealth Management. If they gave a low rating "
            f"on any question, acknowledge it and assure them that the team will work to "
            f"improve. Remind them that {call.get_variable('advisor')} is always available if they have any "
            f"questions about their portfolio, and wish them a great day before closing the call."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Client satisfaction survey for wealth management clients."
    )
    parser.add_argument("phone", help="The phone number to call (E.164 format, e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Full name of the client")
    parser.add_argument(
        "--advisor",
        default="your advisor",
        help="Full name of the client's assigned advisor (default: 'your advisor')",
    )
    args = parser.parse_args()

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "contact_name": args.name,
            "advisor": args.advisor,
        },
    )

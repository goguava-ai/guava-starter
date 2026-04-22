import argparse
import json
import os
from datetime import datetime

import guava
from guava import logging_utils

agent = guava.Agent(
    name="Morgan",
    organization="Metro Power & Light",
    purpose=(
        "conduct a brief post-interaction satisfaction survey to understand the customer's "
        "experience, collect Net Promoter Score data, and identify areas where Metro Power "
        "& Light can improve its service"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(contact_full_name=call.get_variable("contact_name"))


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    if outcome == "unavailable":
        results = {
            "timestamp": datetime.now().isoformat(),
            "contact_name": call.get_variable("contact_name"),
            "account_number": call.get_variable("account_number"),
            "interaction_type": call.get_variable("interaction_type"),
            "interaction_date": call.get_variable("interaction_date"),
            "status": "recipient_unavailable",
        }
        print(json.dumps(results, indent=2))
        call.hangup(
            final_instructions=(
                "Leave a brief voicemail letting the customer know that Metro Power & Light called "
                "to gather feedback about their recent experience. Let them know their opinion matters "
                "and invite them to complete a short survey online at metropowerandlight.com/feedback "
                "at their convenience. Thank them for being a customer."
            )
        )
    elif outcome == "available":
        contact_name = call.get_variable("contact_name")
        account_number = call.get_variable("account_number")
        interaction_type = call.get_variable("interaction_type")
        interaction_date = call.get_variable("interaction_date")
        call.set_task(
            "satisfaction_survey",
            objective=(
                f"Conduct a post-interaction satisfaction survey with {contact_name} "
                f"(account {account_number}) regarding {interaction_type} on "
                f"{interaction_date}. Collect an NPS score, satisfaction and helpfulness "
                "ratings, confirm whether their issue was resolved, assess wait time acceptability, "
                "and invite any suggestions for improvement. Keep the survey conversational, "
                "brief, and thank the customer for their feedback."
            ),
            checklist=[
                guava.Say(
                    f"Hi {contact_name.split()[0]}, this is Morgan calling from Metro Power & Light. "
                    f"I'm following up on {interaction_type} on {interaction_date}. "
                    f"We'd love to get your feedback — this survey takes about two minutes and your "
                    f"responses help us improve our service. Do you have a moment?"
                ),
                guava.Field(
                    key="nps_score",
                    description=(
                        "Ask: On a scale of 0 to 10, where 0 is not at all likely and 10 is extremely likely, "
                        "how likely are you to recommend Metro Power & Light to a friend or family member?"
                    ),
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="interaction_satisfaction_rating",
                    description=(
                        "Ask: On a scale of 1 to 5, where 1 is very dissatisfied and 5 is very satisfied, "
                        "how satisfied were you with your overall experience during this interaction?"
                    ),
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="issue_resolved",
                    description=(
                        "Ask whether the customer's issue or request was fully resolved during "
                        "their interaction with Metro Power & Light"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="wait_time_acceptable",
                    description=(
                        "Ask whether the customer found the wait time to reach a representative "
                        "acceptable during their interaction"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="agent_helpfulness_rating",
                    description=(
                        "Ask: On a scale of 1 to 5, where 1 is not helpful at all and 5 is extremely helpful, "
                        "how would you rate the helpfulness of the representative you spoke with?"
                    ),
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="improvement_suggestions",
                    description=(
                        "Ask whether the customer has any suggestions for how Metro Power & Light "
                        "could improve its service or the experience they had"
                    ),
                    field_type="text",
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("satisfaction_survey")
def on_done(call: guava.Call) -> None:
    results = {
        "timestamp": datetime.now().isoformat(),
        "contact_name": call.get_variable("contact_name"),
        "account_number": call.get_variable("account_number"),
        "interaction_type": call.get_variable("interaction_type"),
        "interaction_date": call.get_variable("interaction_date"),
        "fields": {
            "nps_score": call.get_field("nps_score"),
            "interaction_satisfaction_rating": call.get_field("interaction_satisfaction_rating"),
            "issue_resolved": call.get_field("issue_resolved"),
            "wait_time_acceptable": call.get_field("wait_time_acceptable"),
            "agent_helpfulness_rating": call.get_field("agent_helpfulness_rating"),
            "improvement_suggestions": call.get_field("improvement_suggestions"),
        },
    }
    print(json.dumps(results, indent=2))
    call.hangup(
        final_instructions=(
            "Thank the customer sincerely for taking the time to complete the survey. Let them know "
            "their feedback is reviewed by the Metro Power & Light team and used to improve customer "
            "service. If their satisfaction or NPS score was low (3 or below), acknowledge their "
            "experience, apologize for falling short, and let them know their feedback will be "
            "escalated. Wish them a good day."
        )
    )


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
    args = parser.parse_args()

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "contact_name": args.name,
            "account_number": args.account_number,
            "interaction_type": args.interaction_type,
            "interaction_date": args.interaction_date,
        },
    )

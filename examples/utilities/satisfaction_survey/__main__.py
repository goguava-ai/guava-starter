import guava
import os
import logging
from guava import logging_utils
import json
import argparse
from datetime import datetime



class SatisfactionSurveyController(guava.CallController):
    def __init__(self, contact_name, account_number, interaction_type, interaction_date):
        super().__init__()
        self.contact_name = contact_name
        self.account_number = account_number
        self.interaction_type = interaction_type
        self.interaction_date = interaction_date

        self.set_persona(
            organization_name="Metro Power & Light",
            agent_name="Morgan",
            agent_purpose=(
                "conduct a brief post-interaction satisfaction survey to understand the customer's "
                "experience, collect Net Promoter Score data, and identify areas where Metro Power "
                "& Light can improve its service"
            ),
        )

        self.reach_person(
            contact_full_name=self.contact_name,
            on_success=self.begin_survey,
            on_failure=self.recipient_unavailable,
        )

    def begin_survey(self):
        self.set_task(
            objective=(
                f"Conduct a post-interaction satisfaction survey with {self.contact_name} "
                f"(account {self.account_number}) regarding {self.interaction_type} on "
                f"{self.interaction_date}. Collect an NPS score, satisfaction and helpfulness "
                "ratings, confirm whether their issue was resolved, assess wait time acceptability, "
                "and invite any suggestions for improvement. Keep the survey conversational, "
                "brief, and thank the customer for their feedback."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.contact_name.split()[0]}, this is Morgan calling from Metro Power & Light. "
                    f"I'm following up on {self.interaction_type} on {self.interaction_date}. "
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
            on_complete=self.save_results,
        )

    def recipient_unavailable(self):
        results = {
            "timestamp": datetime.now().isoformat(),
            "contact_name": self.contact_name,
            "account_number": self.account_number,
            "interaction_type": self.interaction_type,
            "interaction_date": self.interaction_date,
            "status": "recipient_unavailable",
        }
        print(json.dumps(results, indent=2))
        self.hangup(
            final_instructions=(
                "Leave a brief voicemail letting the customer know that Metro Power & Light called "
                "to gather feedback about their recent experience. Let them know their opinion matters "
                "and invite them to complete a short survey online at metropowerandlight.com/feedback "
                "at their convenience. Thank them for being a customer."
            )
        )

    def save_results(self):
        results = {
            "timestamp": datetime.now().isoformat(),
            "contact_name": self.contact_name,
            "account_number": self.account_number,
            "interaction_type": self.interaction_type,
            "interaction_date": self.interaction_date,
            "fields": {
                "nps_score": self.get_field("nps_score"),
                "interaction_satisfaction_rating": self.get_field("interaction_satisfaction_rating"),
                "issue_resolved": self.get_field("issue_resolved"),
                "wait_time_acceptable": self.get_field("wait_time_acceptable"),
                "agent_helpfulness_rating": self.get_field("agent_helpfulness_rating"),
                "improvement_suggestions": self.get_field("improvement_suggestions"),
            },
        }
        print(json.dumps(results, indent=2))
        self.hangup(
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

    controller = SatisfactionSurveyController(
        contact_name=args.name,
        account_number=args.account_number,
        interaction_type=args.interaction_type,
        interaction_date=args.interaction_date,
    )

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=controller,
    )

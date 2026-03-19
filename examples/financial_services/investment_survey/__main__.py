import guava
import os
import logging
import json
import argparse
from datetime import datetime

logging.basicConfig(level=logging.INFO)


class InvestmentSurveyController(guava.CallController):
    def __init__(self, contact_name: str, advisor: str):
        super().__init__()
        self.contact_name = contact_name
        self.advisor = advisor

        self.set_persona(
            organization_name="First National Wealth Management",
            agent_name="Sam",
            agent_purpose=(
                "to conduct a brief client satisfaction survey covering advisor performance, "
                "portfolio satisfaction, and overall service quality"
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
                f"You are conducting a client satisfaction survey on behalf of First National "
                f"Wealth Management. You are speaking with {self.contact_name}, a client of "
                f"{self.advisor}. The survey is designed to gather structured feedback on advisor "
                f"performance, portfolio satisfaction, and service quality for CRM and compliance "
                f"reporting. Keep the tone warm, respectful, and efficient. This survey should "
                f"take no more than 5 minutes. Thank the client for their time at each step and "
                f"reassure them that their feedback is confidential and will be used to improve "
                f"their experience."
            ),
            checklist=[
                guava.Say(
                    f"Hello {self.contact_name}, this is Sam calling from First National Wealth "
                    f"Management. I am reaching out today to gather a few minutes of feedback about "
                    f"your experience with us. Your responses help us ensure we are delivering the "
                    f"best possible service. Everything you share is confidential. Do you have about "
                    f"5 minutes?"
                ),
                guava.Say(
                    f"Great, let's get started. The first question is about your advisor, "
                    f"{self.advisor}."
                ),
                guava.Field(
                    key="advisor_rating",
                    description=(
                        f"Ask the client to rate their overall satisfaction with {self.advisor} "
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
            on_complete=self.save_results,
        )

    def save_results(self):
        results = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "contact_name": self.contact_name,
            "advisor": self.advisor,
            "advisor_rating": self.get_field("advisor_rating"),
            "portfolio_satisfaction": self.get_field("portfolio_satisfaction"),
            "service_quality_rating": self.get_field("service_quality_rating"),
            "likelihood_to_recommend": self.get_field("likelihood_to_recommend"),
            "improvement_suggestions": self.get_field("improvement_suggestions"),
        }
        print(json.dumps(results, indent=2))
        self.hangup(
            final_instructions=(
                f"Thank {self.contact_name} sincerely for taking the time to complete the survey. "
                f"Let them know their feedback is genuinely valued and will be reviewed by the "
                f"leadership team at First National Wealth Management. If they gave a low rating "
                f"on any question, acknowledge it and assure them that the team will work to "
                f"improve. Remind them that {self.advisor} is always available if they have any "
                f"questions about their portfolio, and wish them a great day before closing the call."
            )
        )

    def recipient_unavailable(self):
        self.hangup(
            final_instructions=(
                f"You were unable to reach {self.contact_name}. Leave a brief, friendly voicemail "
                f"identifying yourself as Sam from First National Wealth Management. Let them know "
                f"you were calling to gather a few minutes of feedback about their experience with "
                f"us, and that their input is very important to us. Ask them to call back at their "
                f"convenience or mention that you may follow up at another time."
            )
        )


if __name__ == "__main__":
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

    controller = InvestmentSurveyController(
        contact_name=args.name,
        advisor=args.advisor,
    )

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=controller,
    )

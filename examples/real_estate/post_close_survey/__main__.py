import guava
import os
import logging
import json
import argparse
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)


class PostCloseSurveyController(guava.CallController):
    def __init__(self, contact_name: str, agent_name: str, property_address: str):
        super().__init__()
        self.contact_name = contact_name
        self.agent_name = agent_name
        self.property_address = property_address
        self.set_persona(
            organization_name="Pinnacle Realty Group",
            agent_name="Morgan",
            agent_purpose=(
                "gather post-closing feedback from buyers and sellers to help "
                "Pinnacle Realty Group improve agent performance and invite satisfied "
                "clients to join the referral program"
            ),
        )
        self.reach_person(
            contact_full_name=self.contact_name,
            on_success=self.start_survey,
            on_failure=self.recipient_unavailable,
        )

    def start_survey(self):
        self.set_task(
            objective=(
                f"You are calling {self.contact_name} to congratulate them on the recent "
                f"closing of {self.property_address} and gather their feedback about their "
                f"experience working with {self.agent_name} at Pinnacle Realty Group. "
                "Be warm, celebratory, and genuinely curious. Let them know their feedback "
                "directly shapes how agents are recognized and how the company improves. "
                "Keep the tone conversational — this is a celebration call, not a cold survey."
            ),
            checklist=[
                guava.Say(
                    f"Congratulations again on your recent closing at {self.property_address}! "
                    f"On behalf of everyone at Pinnacle Realty Group, we're so excited for you. "
                    f"I'm Morgan, and I'm reaching out to hear about your experience with "
                    f"{self.agent_name}. Your feedback means a great deal to our team and "
                    f"only takes a few minutes."
                ),
                guava.Field(
                    key="overall_experience_rating",
                    description=(
                        "On a scale of 1 to 5, with 5 being excellent and 1 being poor, "
                        "how would you rate your overall experience with Pinnacle Realty Group "
                        "from start to close?"
                    ),
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="agent_communication_rating",
                    description=(
                        f"Still using a scale of 1 to 5, how would you rate {self.agent_name}'s "
                        "communication throughout the process — things like responsiveness, "
                        "keeping you informed, and explaining each step clearly?"
                    ),
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="would_recommend",
                    description=(
                        "Would you recommend Pinnacle Realty Group to a friend, family member, "
                        "or colleague who is buying or selling a home?"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="most_helpful_aspect",
                    description=(
                        "What was the most helpful or memorable part of working with "
                        f"{self.agent_name} or our team during this transaction?"
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="areas_for_improvement",
                    description=(
                        "Is there anything we could have done better or differently "
                        "to make your experience even smoother?"
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="open_to_referral_program",
                    description=(
                        "We have a referral program that rewards clients who connect us with "
                        "new buyers or sellers. Would you be interested in learning more about it?"
                    ),
                    field_type="text",
                    required=True,
                ),
            ],
            on_complete=self.save_results,
        )

    def save_results(self):
        overall = self.get_field("overall_experience_rating")
        communication = self.get_field("agent_communication_rating")
        referral_interest = (self.get_field("open_to_referral_program") or "").lower()

        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "vertical": "real_estate",
            "use_case": "post_close_survey",
            "contact_name": self.contact_name,
            "agent_name": self.agent_name,
            "property_address": self.property_address,
            "fields": {
                "overall_experience_rating": overall,
                "agent_communication_rating": communication,
                "would_recommend": self.get_field("would_recommend"),
                "most_helpful_aspect": self.get_field("most_helpful_aspect"),
                "areas_for_improvement": self.get_field("areas_for_improvement"),
                "open_to_referral_program": self.get_field("open_to_referral_program"),
            },
        }
        print(json.dumps(results, indent=2))
        logging.info("Post-close survey results captured: %s", results)

        referral_note = (
            "Also mention that someone from our team will be in touch shortly with "
            "details about the referral program and how they can earn rewards for "
            "connecting us with new clients. "
            if any(word in referral_interest for word in ["yes", "sure", "interested", "open"])
            else ""
        )

        self.hangup(
            final_instructions=(
                f"Thank {self.contact_name} sincerely for taking the time to share their "
                f"feedback — let them know it will be shared directly with {self.agent_name} "
                "and the Pinnacle leadership team. "
                + referral_note +
                "Congratulate them once more on their closing, wish them all the best in "
                "their new home or next chapter, and close the call warmly and genuinely."
            )
        )

    def recipient_unavailable(self):
        logging.warning(
            "Could not reach %s for post-close survey (agent: %s, property: %s).",
            self.contact_name,
            self.agent_name,
            self.property_address,
        )
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "vertical": "real_estate",
            "use_case": "post_close_survey",
            "contact_name": self.contact_name,
            "agent_name": self.agent_name,
            "property_address": self.property_address,
            "status": "recipient_unavailable",
        }
        print(json.dumps(results, indent=2))
        self.hangup(
            final_instructions=(
                f"Leave a brief, warm voicemail for {self.contact_name}. "
                "Introduce yourself as Morgan from Pinnacle Realty Group and congratulate "
                f"them on their recent closing at {self.property_address}. "
                "Let them know you're calling to gather a few minutes of feedback about "
                f"their experience with {self.agent_name} and to share information about "
                "a client referral program. Ask them to call back when convenient. "
                "Keep it upbeat and under 30 seconds."
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Post-close satisfaction survey outbound call."
    )
    parser.add_argument("phone", help="The client's phone number to call.")
    parser.add_argument("--name", required=True, help="Full name of the client to reach.")
    parser.add_argument(
        "--agent-name",
        required=True,
        help="Full name of the agent who handled the transaction.",
    )
    parser.add_argument(
        "--property-address",
        required=True,
        help="Address of the property that was bought or sold.",
    )
    args = parser.parse_args()

    logging.info(
        "Initiating post-close survey call to %s (%s) for property %s (agent: %s).",
        args.name,
        args.phone,
        args.property_address,
        args.agent_name,
    )

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=PostCloseSurveyController(
            contact_name=args.name,
            agent_name=args.agent_name,
            property_address=args.property_address,
        ),
    )

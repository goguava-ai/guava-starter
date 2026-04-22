import guava
import os
import logging
import json
import argparse
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)


class LeadQualificationController(guava.CallController):
    def __init__(self):
        super().__init__()
        self.set_persona(
            organization_name="Pinnacle Realty Group",
            agent_name="Jordan",
            agent_purpose=(
                "qualify inbound real estate inquiry leads by understanding their "
                "intent, budget, and timeline so we can connect them with the right agent"
            ),
        )
        self.set_task(
            objective=(
                "Warmly greet the caller and let them know you're here to help match "
                "them with the best agent at Pinnacle Realty Group. Gather key details "
                "about their real estate needs so an agent can follow up with a "
                "personalized plan. Be conversational, reassuring, and professional."
            ),
            checklist=[
                guava.Say(
                    "Hello! Thank you for reaching out to Pinnacle Realty Group. "
                    "My name is Jordan, and I'm here to help connect you with the "
                    "perfect agent for your needs. This will just take a few minutes."
                ),
                guava.Field(
                    key="buyer_or_seller",
                    description="Are you looking to buy a property, sell a property, or both?",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="property_type",
                    description=(
                        "What type of property are you interested in? "
                        "Options include single family home, condo, multi-family, or land."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="target_location",
                    description=(
                        "What city, neighborhood, or general area are you targeting? "
                        "Feel free to mention multiple areas if you're flexible."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="budget_range",
                    description=(
                        "What is your approximate budget or price range for this transaction?"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="timeline_to_move",
                    description=(
                        "What is your ideal timeline? For example, are you looking to "
                        "move within 30 days, 3 months, 6 months, or is it more open-ended?"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="financing_pre_approved",
                    description=(
                        "Have you already been pre-approved for financing, or are you "
                        "paying cash? If not yet pre-approved, that's completely fine."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="agent_assignment_preference",
                    description=(
                        "Do you have a preference for working with a specific agent, "
                        "or would you like us to match you based on your needs and location?"
                    ),
                    field_type="text",
                    required=False,
                ),
            ],
            on_complete=self.save_results,
        )
        accept_call()

    def save_results(self):
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "vertical": "real_estate",
            "use_case": "lead_qualification",
            "fields": {
                "buyer_or_seller": self.get_field("buyer_or_seller"),
                "property_type": self.get_field("property_type"),
                "target_location": self.get_field("target_location"),
                "budget_range": self.get_field("budget_range"),
                "timeline_to_move": self.get_field("timeline_to_move"),
                "financing_pre_approved": self.get_field("financing_pre_approved"),
                "agent_assignment_preference": self.get_field("agent_assignment_preference"),
            },
        }
        print(json.dumps(results, indent=2))
        logging.info("Lead qualification results captured: %s", results)
        self.hangup(
            final_instructions=(
                "Thank the caller sincerely for their time. Let them know that a "
                "Pinnacle Realty Group agent will be reaching out to them within one "
                "business day to discuss their needs in detail and put together a "
                "personalized plan. Wish them a wonderful day and say goodbye warmly."
            )
        )


def accept_call():
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=LeadQualificationController,
    )


if __name__ == "__main__":
    logging.info("Starting Lead Qualification inbound agent for Pinnacle Realty Group.")
    accept_call()

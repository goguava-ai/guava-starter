import guava
import os
import logging
import json
import argparse
import requests
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)


class OutboundLeadQualificationController(guava.CallController):
    def __init__(self, prospect_name: str):
        super().__init__()
        self.prospect_name = prospect_name

        self.set_persona(
            organization_name="Velocity Sales Group",
            agent_name="Alex",
            agent_purpose=(
                "to reach prospective customers, introduce Velocity's solutions, "
                "qualify their interest and budget, and capture key lead information"
            ),
        )

        self.reach_person(
            contact_full_name=self.prospect_name,
            on_success=self.begin_qualification,
            on_failure=self.recipient_unavailable,
        )

    def begin_qualification(self):
        self.set_task(
            objective=(
                f"You've reached {self.prospect_name}. Introduce yourself and Velocity Sales Group, "
                "then qualify this lead by collecting their interest level, product preferences, "
                "budget range, and decision timeline. Be conversational and not pushy."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.prospect_name}, this is Alex calling from Velocity Sales Group. "
                    "Thanks for taking my call — I'd love to take just a few minutes to learn "
                    "about your needs and see if we might be a good fit."
                ),
                guava.Field(
                    key="interest_level",
                    description=(
                        "Gauge the prospect's interest level in learning more. "
                        "Categorize as: very_interested, somewhat_interested, or not_interested."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="product_interest",
                    description=(
                        "Ask which of Velocity's product lines they're most interested in. "
                        "Capture the specific product or service area they mention."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="budget_range",
                    description=(
                        "Ask about their approximate budget range for this type of solution. "
                        "Capture the range they provide or note if they prefer not to share."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="decision_timeline",
                    description=(
                        "Ask when they're looking to make a decision — this quarter, "
                        "this year, or just exploring. Capture their timeline."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="follow_up_preference",
                    description=(
                        "Ask how they'd prefer to be followed up with — email, phone call, "
                        "or a scheduled demo. Capture their preference."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="additional_notes",
                    description=(
                        "Capture any other relevant details the prospect shares about their "
                        "needs, concerns, or current solutions they use."
                    ),
                    field_type="text",
                    required=False,
                ),
            ],
            on_complete=self.save_results,
        )

    def save_results(self):
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": "Alex",
            "organization": "Velocity Sales Group",
            "use_case": "outbound_lead_qualification",
            "prospect_name": self.prospect_name,
            "fields": {
                "interest_level": self.get_field("interest_level"),
                "product_interest": self.get_field("product_interest"),
                "budget_range": self.get_field("budget_range"),
                "decision_timeline": self.get_field("decision_timeline"),
                "follow_up_preference": self.get_field("follow_up_preference"),
                "additional_notes": self.get_field("additional_notes"),
            },
        }
        print(json.dumps(results, indent=2))
        logging.info("Lead qualification results saved locally.")

        # Push call tracking data to Ringba
        try:
            api_url = os.environ["RINGBA_API_URL"]
            token = os.environ["RINGBA_API_TOKEN"]
            account_id = os.environ["RINGBA_ACCOUNT_ID"]
            campaign_id = os.environ["RINGBA_CAMPAIGN_ID"]
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            call_payload = {
                "prospectName": self.prospect_name,
                "interestLevel": self.get_field("interest_level"),
                "productInterest": self.get_field("product_interest"),
                "budgetRange": self.get_field("budget_range"),
                "decisionTimeline": self.get_field("decision_timeline"),
                "followUpPreference": self.get_field("follow_up_preference"),
                "additionalNotes": self.get_field("additional_notes"),
                "callTimestamp": datetime.now(timezone.utc).isoformat(),
                "source": "guava_voice_agent",
            }
            resp = requests.post(
                f"{api_url}/v2/{account_id}/campaigns/{campaign_id}/calls",
                headers=headers,
                json=call_payload,
                timeout=10,
            )
            resp.raise_for_status()
            logging.info("Ringba call data pushed successfully.")
        except Exception as e:
            logging.error("Failed to push to Ringba: %s", e)

        self.hangup(
            final_instructions=(
                "Thank the prospect for their time. Let them know a Velocity team member "
                "will follow up based on their preference. Wish them a great day."
            )
        )

    def recipient_unavailable(self):
        self.hangup(
            final_instructions=(
                "We were unable to reach the prospect. Leave a brief, professional voicemail "
                "introducing Velocity Sales Group and asking them to call back at their "
                "convenience. Provide a callback number if available."
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Outbound lead qualification call for Velocity Sales Group."
    )
    parser.add_argument("phone", help="Prospect phone number to call")
    parser.add_argument("--name", required=True, help="Full name of the prospect")
    args = parser.parse_args()

    logging.info(
        "Initiating lead qualification call to %s (%s)",
        args.name,
        args.phone,
    )

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=OutboundLeadQualificationController(
            prospect_name=args.name,
        ),
    )

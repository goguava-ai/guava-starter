import guava
import os
import logging
from guava import logging_utils
import json
import argparse
from datetime import datetime, timezone



class ChurnPreventionController(guava.CallController):
    def __init__(self, contact_name, account_number, current_plan, tenure_months):
        super().__init__()
        self.contact_name = contact_name
        self.account_number = account_number
        self.current_plan = current_plan
        self.tenure_months = tenure_months

        self.set_persona(
            organization_name="Nexus Mobile",
            agent_name="Jordan",
            agent_purpose=(
                "to speak with valued Nexus Mobile subscribers who may be considering "
                "leaving, understand their concerns, and present personalized retention "
                "options to help them get the most out of their service"
            ),
        )

        self.reach_person(
            contact_full_name=self.contact_name,
            on_success=self.begin_retention_flow,
            on_failure=self.recipient_unavailable,
        )

    def begin_retention_flow(self):
        self.set_task(
            objective=(
                f"You are speaking with {self.contact_name}, a Nexus Mobile customer "
                f"on the {self.current_plan} plan who has been with us for "
                f"{self.tenure_months} months (account #{self.account_number}). "
                "Your goal is to understand why they may be considering cancellation, "
                "present relevant retention offers, and document their final decision. "
                "Be empathetic, listen carefully, and avoid being pushy."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.contact_name.split()[0]}, thank you so much for taking my call today. "
                    f"I'm reaching out because we truly value your loyalty over the past "
                    f"{self.tenure_months} months and want to make sure you're completely "
                    f"happy with your Nexus Mobile experience."
                ),
                guava.Field(
                    key="primary_dissatisfaction_reason",
                    description=(
                        "Ask the customer what their primary reason for dissatisfaction or "
                        "consideration of leaving is. Listen openly and capture the core issue "
                        "(e.g. price, coverage, data speeds, customer service, competitor offer)."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="competitor_offer_received",
                    description=(
                        "Ask if the customer has received or is considering a specific offer "
                        "from a competitor. If yes, capture the competitor name and any details "
                        "they are willing to share. If no, note that."
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="alternative_plan_interest",
                    description=(
                        "Based on the dissatisfaction reason, present one or two alternative "
                        "Nexus Mobile plans or add-ons that could address their concern. "
                        "Ask if any of these options sound interesting to them and capture "
                        "their response."
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="retention_offer_accepted",
                    description=(
                        "Present the best available retention offer (e.g. a discount, free month, "
                        "plan credit, or free add-on). Ask if the customer would like to accept "
                        "this offer to stay with Nexus Mobile. Capture their answer clearly."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="cancellation_decision",
                    description=(
                        "Ask for the customer's final decision: will they stay with Nexus Mobile, "
                        "request more time to decide, or proceed with cancellation? "
                        "Capture their exact decision."
                    ),
                    field_type="text",
                    required=True,
                ),
            ],
            on_complete=self.save_results,
        )

    def save_results(self):
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": "Jordan",
            "organization": "Nexus Mobile",
            "use_case": "churn_prevention",
            "contact_name": self.contact_name,
            "account_number": self.account_number,
            "current_plan": self.current_plan,
            "tenure_months": self.tenure_months,
            "fields": {
                "primary_dissatisfaction_reason": self.get_field("primary_dissatisfaction_reason"),
                "competitor_offer_received": self.get_field("competitor_offer_received"),
                "alternative_plan_interest": self.get_field("alternative_plan_interest"),
                "retention_offer_accepted": self.get_field("retention_offer_accepted"),
                "cancellation_decision": self.get_field("cancellation_decision"),
            },
        }
        print(json.dumps(results, indent=2))
        logging.info("Churn prevention call results saved.")
        self.hangup(
            final_instructions=(
                "Thank the customer sincerely for their time and honesty. If they are staying, "
                "confirm any offer details and let them know a confirmation will be sent. "
                "If they are leaving, express genuine regret, remind them Nexus Mobile's door "
                "is always open, and wish them well."
            )
        )

    def recipient_unavailable(self):
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": "Jordan",
            "organization": "Nexus Mobile",
            "use_case": "churn_prevention",
            "contact_name": self.contact_name,
            "account_number": self.account_number,
            "status": "recipient_unavailable",
        }
        print(json.dumps(results, indent=2))
        logging.info("Recipient unavailable for churn prevention call.")
        self.hangup(
            final_instructions=(
                "The contact was not available. End the call politely without leaving "
                "sensitive account details in a voicemail."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Nexus Mobile — Churn Prevention outbound call agent"
    )
    parser.add_argument("phone", help="Customer phone number to call (E.164 format)")
    parser.add_argument("--name", required=True, help="Full name of the customer")
    parser.add_argument("--account-number", required=True, help="Customer account number")
    parser.add_argument("--current-plan", required=True, help="Customer's current plan name")
    parser.add_argument(
        "--tenure-months",
        required=True,
        help="Number of months the customer has been with Nexus Mobile",
    )
    args = parser.parse_args()

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=ChurnPreventionController(
            contact_name=args.name,
            account_number=args.account_number,
            current_plan=args.current_plan,
            tenure_months=args.tenure_months,
        ),
    )

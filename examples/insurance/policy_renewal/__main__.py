import guava
import os
import logging
from guava import logging_utils
import json
import argparse
from datetime import datetime, timezone



class PolicyRenewalController(guava.CallController):
    def __init__(self, contact_name: str, policy_number: str, renewal_date: str):
        super().__init__()
        self.contact_name = contact_name
        self.policy_number = policy_number
        self.renewal_date = renewal_date

        self.set_persona(
            organization_name="Keystone Property & Casualty",
            agent_name="Riley",
            agent_purpose=(
                "to reach out to policyholders ahead of their renewal date to confirm "
                "their coverage needs, answer questions, and ensure a smooth renewal process"
            ),
        )
        self.reach_person(
            contact_full_name=self.contact_name,
            on_success=self.start_renewal_flow,
            on_failure=self.recipient_unavailable,
        )

    def start_renewal_flow(self):
        self.set_task(
            objective=(
                f"You are calling {self.contact_name} regarding policy number "
                f"{self.policy_number}, which is coming up for renewal {self.renewal_date}. "
                "Confirm whether they would like to renew as-is, if they need any coverage "
                "changes, or if they have questions. Explore whether any additional coverage "
                "types may benefit them based on life changes. Capture their preferred payment "
                "method for the renewal. Be warm, consultative, and flag any upsell or "
                "retention risk for the account team."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.contact_name}, this is Riley calling from Keystone Property "
                    f"& Casualty. I'm reaching out because your policy number {self.policy_number} "
                    f"is coming up for renewal {self.renewal_date}, and I wanted to take a few "
                    "minutes to make sure everything still looks right for you."
                ),
                guava.Field(
                    key="renewal_confirmed",
                    description=(
                        "Whether the policyholder wants to renew: yes, no, or need_changes"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="coverage_change_requested",
                    description=(
                        "Description of any coverage changes the policyholder would like "
                        "to make at renewal, if any"
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="additional_coverage_interest",
                    description=(
                        "Any additional coverage types the policyholder expressed interest in, "
                        "such as umbrella, flood, jewelry riders, or identity theft protection"
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="preferred_payment_method",
                    description=(
                        "The policyholder's preferred payment method for the renewal premium, "
                        "such as autopay, check, credit card, or bank transfer"
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
            "use_case": "policy_renewal",
            "contact_name": self.contact_name,
            "policy_number": self.policy_number,
            "renewal_date": self.renewal_date,
            "renewal_confirmed": self.get_field("renewal_confirmed"),
            "coverage_change_requested": self.get_field("coverage_change_requested"),
            "additional_coverage_interest": self.get_field("additional_coverage_interest"),
            "preferred_payment_method": self.get_field("preferred_payment_method"),
        }
        print(json.dumps(results, indent=2))
        logging.info("Policy renewal results saved: %s", results)
        self.hangup(
            final_instructions=(
                "Thank you so much for taking the time to speak with me today. Your renewal "
                "preferences have been noted, and a member of our team will follow up with "
                "any updated policy documents or next steps before the renewal date. "
                "We truly appreciate your continued trust in Keystone Property & Casualty. "
                "Have a wonderful day."
            )
        )

    def recipient_unavailable(self):
        logging.warning(
            "Could not reach %s for policy renewal on policy %s.",
            self.contact_name,
            self.policy_number,
        )
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "use_case": "policy_renewal",
            "contact_name": self.contact_name,
            "policy_number": self.policy_number,
            "renewal_date": self.renewal_date,
            "outcome": "recipient_unavailable",
        }
        print(json.dumps(results, indent=2))
        self.hangup(
            final_instructions=(
                "We were unable to reach the policyholder. Please schedule a callback attempt."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound policy renewal call for Keystone Property & Casualty"
    )
    parser.add_argument("phone", help="Phone number to dial")
    parser.add_argument("--name", required=True, help="Full name of the policyholder")
    parser.add_argument("--policy-number", required=True, help="Policy number")
    parser.add_argument(
        "--renewal-date",
        default="in 30 days",
        help="Renewal date or description (default: 'in 30 days')",
    )
    args = parser.parse_args()

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=PolicyRenewalController(
            contact_name=args.name,
            policy_number=args.policy_number,
            renewal_date=args.renewal_date,
        ),
    )

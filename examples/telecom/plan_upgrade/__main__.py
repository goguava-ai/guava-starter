import guava
import os
import logging
import json
import argparse
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)


class PlanUpgradeController(guava.CallController):
    def __init__(self, contact_name, account_number, current_plan, new_plan, price_difference):
        super().__init__()
        self.contact_name = contact_name
        self.account_number = account_number
        self.current_plan = current_plan
        self.new_plan = new_plan
        self.price_difference = price_difference

        self.set_persona(
            organization_name="Nexus Mobile",
            agent_name="Riley",
            agent_purpose=(
                "to inform Nexus Mobile customers currently on legacy plans about exciting "
                "new plan options available to them and to assist them in upgrading to a "
                "plan that better fits their needs"
            ),
        )

        self.reach_person(
            contact_full_name=self.contact_name,
            on_success=self.begin_upgrade_flow,
            on_failure=self.recipient_unavailable,
        )

    def begin_upgrade_flow(self):
        self.set_task(
            objective=(
                f"You are speaking with {self.contact_name}, a Nexus Mobile customer "
                f"currently on the {self.current_plan} plan (account #{self.account_number}). "
                f"You are calling to introduce the {self.new_plan} plan, which is "
                f"{self.price_difference}. Explain the key benefits of the new plan clearly "
                "and honestly, answer any questions, and document whether the customer "
                "wishes to upgrade."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.contact_name.split()[0]}, this is Riley calling from Nexus Mobile. "
                    f"I'm reaching out today because we have some exciting new plan options "
                    f"and I wanted to make sure you knew about an upgrade that could be a "
                    f"great fit for you."
                ),
                guava.Field(
                    key="interested_in_upgrade",
                    description=(
                        f"Introduce the {self.new_plan} plan and explain that it is "
                        f"{self.price_difference} compared to their current {self.current_plan} plan. "
                        "Highlight the top two or three benefits of the new plan. "
                        "Ask the customer if they are interested in hearing more or in upgrading. "
                        "Capture their initial level of interest."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="questions_about_new_plan",
                    description=(
                        "Ask if the customer has any questions about the new plan, pricing, "
                        "features, or the upgrade process. Answer any questions thoroughly "
                        "and capture a summary of the questions they asked."
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="upgrade_plan_selected",
                    description=(
                        f"If the customer is interested, confirm that they would like to upgrade "
                        f"to the {self.new_plan} plan specifically. If they express interest in "
                        "a different plan tier, capture that instead. If they are not interested "
                        "in any upgrade, note that here."
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="upgrade_effective_date_preference",
                    description=(
                        "If the customer wants to upgrade, ask when they would like the new plan "
                        "to take effect — immediately, at the start of their next billing cycle, "
                        "or on a specific date. Capture their preference."
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="upgrade_decision_final",
                    description=(
                        "Confirm the customer's final decision: upgrading now, upgrading later, "
                        "wanting a follow-up call, or declining the upgrade entirely. "
                        "Capture this conclusively."
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
            "agent": "Riley",
            "organization": "Nexus Mobile",
            "use_case": "plan_upgrade",
            "contact_name": self.contact_name,
            "account_number": self.account_number,
            "current_plan": self.current_plan,
            "new_plan": self.new_plan,
            "price_difference": self.price_difference,
            "fields": {
                "interested_in_upgrade": self.get_field("interested_in_upgrade"),
                "questions_about_new_plan": self.get_field("questions_about_new_plan"),
                "upgrade_plan_selected": self.get_field("upgrade_plan_selected"),
                "upgrade_effective_date_preference": self.get_field("upgrade_effective_date_preference"),
                "upgrade_decision_final": self.get_field("upgrade_decision_final"),
            },
        }
        print(json.dumps(results, indent=2))
        logging.info("Plan upgrade call results saved.")
        self.hangup(
            final_instructions=(
                "Thank the customer warmly for their time. If they are upgrading, confirm "
                "the effective date and let them know they will receive a confirmation. "
                "If they are not upgrading today, let them know they can call Nexus Mobile "
                "any time to make the change and wish them a great day."
            )
        )

    def recipient_unavailable(self):
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": "Riley",
            "organization": "Nexus Mobile",
            "use_case": "plan_upgrade",
            "contact_name": self.contact_name,
            "account_number": self.account_number,
            "status": "recipient_unavailable",
        }
        print(json.dumps(results, indent=2))
        logging.info("Recipient unavailable for plan upgrade call.")
        self.hangup(
            final_instructions=(
                "The contact was not available. End the call politely without disclosing "
                "account details in a voicemail."
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Nexus Mobile — Plan Upgrade outbound call agent"
    )
    parser.add_argument("phone", help="Customer phone number to call (E.164 format)")
    parser.add_argument("--name", required=True, help="Full name of the customer")
    parser.add_argument("--account-number", required=True, help="Customer account number")
    parser.add_argument("--current-plan", required=True, help="Customer's current legacy plan name")
    parser.add_argument("--new-plan", required=True, help="Name of the new plan being offered")
    parser.add_argument(
        "--price-difference",
        required=True,
        help="Price difference description (e.g. '$5 more per month')",
    )
    args = parser.parse_args()

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=PlanUpgradeController(
            contact_name=args.name,
            account_number=args.account_number,
            current_plan=args.current_plan,
            new_plan=args.new_plan,
            price_difference=args.price_difference,
        ),
    )

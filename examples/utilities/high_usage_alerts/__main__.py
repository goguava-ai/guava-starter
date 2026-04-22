import guava
import os
import logging
from guava import logging_utils
import json
import argparse
from datetime import datetime



class HighUsageAlertController(guava.CallController):
    def __init__(self, contact_name, account_number, usage_percent_above, estimated_bill):
        super().__init__()
        self.contact_name = contact_name
        self.account_number = account_number
        self.usage_percent_above = usage_percent_above
        self.estimated_bill = estimated_bill

        self.set_persona(
            organization_name="Metro Power & Light",
            agent_name="Riley",
            agent_purpose=(
                "alert customers whose energy usage is significantly above their normal patterns, "
                "understand whether the increase is expected, and offer energy efficiency resources "
                "and billing programs that may help manage their costs"
            ),
        )

        self.reach_person(
            contact_full_name=self.contact_name,
            on_success=self.begin_alert,
            on_failure=self.recipient_unavailable,
        )

    def begin_alert(self):
        self.set_task(
            objective=(
                f"Speak with {self.contact_name} (account {self.account_number}) about an unusually "
                f"high energy usage pattern detected on their account. Their usage is currently "
                f"{self.usage_percent_above}% above their normal level for this time of year, and "
                f"their estimated bill this month is {self.estimated_bill}. Determine whether the "
                "customer is aware of a reason for the increase, and offer relevant programs: "
                "a free home energy audit, paperless billing, and budget billing (which averages "
                "usage costs across 12 months to avoid high seasonal bills)."
            ),
            checklist=[
                guava.Say(
                    f"Hi {self.contact_name.split()[0]}, this is Riley calling from Metro Power & Light "
                    f"with an important update about your account. We've noticed that your energy usage "
                    f"this billing period is about {self.usage_percent_above}% higher than your typical "
                    f"usage for this time of year. Based on current usage, your estimated bill this month "
                    f"is approximately {self.estimated_bill}. We wanted to reach out so this doesn't come "
                    f"as a surprise and to see if there's anything we can help with."
                ),
                guava.Field(
                    key="usage_increase_acknowledged",
                    description="Ask the customer whether they are aware that their energy usage has been higher than normal this billing period",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="known_reason_for_increase",
                    description="Ask whether the customer knows what may have caused the increase, such as new appliances, houseguests, extreme weather, a new electric vehicle, or changes to their home",
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="interested_in_energy_audit",
                    description="Ask if the customer would be interested in a free home energy audit, where a Metro Power & Light specialist identifies ways to reduce energy consumption and lower bills",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="paperless_billing_interest",
                    description="Ask if the customer would like to sign up for paperless billing to receive instant usage alerts and bill notifications by email",
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="budget_billing_interest",
                    description="Ask if the customer is interested in the budget billing program, which averages their energy costs over 12 months so they pay a predictable amount each month instead of seeing high seasonal bills",
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
            "usage_percent_above": self.usage_percent_above,
            "estimated_bill": self.estimated_bill,
            "status": "recipient_unavailable",
        }
        print(json.dumps(results, indent=2))
        self.hangup(
            final_instructions=(
                "Leave a brief voicemail letting the customer know that Metro Power & Light called "
                "because their energy usage is higher than normal this month and their estimated bill "
                "may be higher than expected. Encourage them to log in to their account at "
                "metropowerandlight.com to view usage details or call back to learn about programs "
                "that can help manage energy costs. Keep the message concise."
            )
        )

    def save_results(self):
        results = {
            "timestamp": datetime.now().isoformat(),
            "contact_name": self.contact_name,
            "account_number": self.account_number,
            "usage_percent_above": self.usage_percent_above,
            "estimated_bill": self.estimated_bill,
            "fields": {
                "usage_increase_acknowledged": self.get_field("usage_increase_acknowledged"),
                "known_reason_for_increase": self.get_field("known_reason_for_increase"),
                "interested_in_energy_audit": self.get_field("interested_in_energy_audit"),
                "paperless_billing_interest": self.get_field("paperless_billing_interest"),
                "budget_billing_interest": self.get_field("budget_billing_interest"),
            },
        }
        print(json.dumps(results, indent=2))
        self.hangup(
            final_instructions=(
                "Summarize any programs the customer expressed interest in and let them know a "
                "follow-up confirmation will be sent. Remind them they can monitor usage anytime "
                "through their online account or the Metro Power & Light app. Thank them for being "
                "a customer and for taking the time to speak with you today."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Metro Power & Light — High Usage Alert Outbound Call"
    )
    parser.add_argument("phone", help="Customer phone number to call")
    parser.add_argument("--name", required=True, help="Customer full name")
    parser.add_argument("--account-number", required=True, help="Customer account number")
    parser.add_argument(
        "--usage-percent-above",
        required=True,
        help="Percentage above normal usage (e.g. '47')",
    )
    parser.add_argument(
        "--estimated-bill",
        required=True,
        help="Estimated bill amount this month (e.g. '$284')",
    )
    args = parser.parse_args()

    controller = HighUsageAlertController(
        contact_name=args.name,
        account_number=args.account_number,
        usage_percent_above=args.usage_percent_above,
        estimated_bill=args.estimated_bill,
    )

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=controller,
    )

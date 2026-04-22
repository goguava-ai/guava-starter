import argparse
import json
import logging
import os
from datetime import datetime

import guava
from guava import logging_utils

agent = guava.Agent(
    name="Riley",
    organization="Metro Power & Light",
    purpose=(
        "alert customers whose energy usage is significantly above their normal patterns, "
        "understand whether the increase is expected, and offer energy efficiency resources "
        "and billing programs that may help manage their costs"
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
            "usage_percent_above": call.get_variable("usage_percent_above"),
            "estimated_bill": call.get_variable("estimated_bill"),
            "status": "recipient_unavailable",
        }
        print(json.dumps(results, indent=2))
        call.hangup(
            final_instructions=(
                "Leave a brief voicemail letting the customer know that Metro Power & Light called "
                "because their energy usage is higher than normal this month and their estimated bill "
                "may be higher than expected. Encourage them to log in to their account at "
                "metropowerandlight.com to view usage details or call back to learn about programs "
                "that can help manage energy costs. Keep the message concise."
            )
        )
    elif outcome == "available":
        contact_name = call.get_variable("contact_name")
        account_number = call.get_variable("account_number")
        usage_percent_above = call.get_variable("usage_percent_above")
        estimated_bill = call.get_variable("estimated_bill")
        call.set_task(
            "high_usage_alert",
            objective=(
                f"Speak with {contact_name} (account {account_number}) about an unusually "
                f"high energy usage pattern detected on their account. Their usage is currently "
                f"{usage_percent_above}% above their normal level for this time of year, and "
                f"their estimated bill this month is {estimated_bill}. Determine whether the "
                "customer is aware of a reason for the increase, and offer relevant programs: "
                "a free home energy audit, paperless billing, and budget billing (which averages "
                "usage costs across 12 months to avoid high seasonal bills)."
            ),
            checklist=[
                guava.Say(
                    f"Hi {contact_name.split()[0]}, this is Riley calling from Metro Power & Light "
                    f"with an important update about your account. We've noticed that your energy usage "
                    f"this billing period is about {usage_percent_above}% higher than your typical "
                    f"usage for this time of year. Based on current usage, your estimated bill this month "
                    f"is approximately {estimated_bill}. We wanted to reach out so this doesn't come "
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
        )


@agent.on_task_complete("high_usage_alert")
def on_done(call: guava.Call) -> None:
    results = {
        "timestamp": datetime.now().isoformat(),
        "contact_name": call.get_variable("contact_name"),
        "account_number": call.get_variable("account_number"),
        "usage_percent_above": call.get_variable("usage_percent_above"),
        "estimated_bill": call.get_variable("estimated_bill"),
        "fields": {
            "usage_increase_acknowledged": call.get_field("usage_increase_acknowledged"),
            "known_reason_for_increase": call.get_field("known_reason_for_increase"),
            "interested_in_energy_audit": call.get_field("interested_in_energy_audit"),
            "paperless_billing_interest": call.get_field("paperless_billing_interest"),
            "budget_billing_interest": call.get_field("budget_billing_interest"),
        },
    }
    print(json.dumps(results, indent=2))
    call.hangup(
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

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "contact_name": args.name,
            "account_number": args.account_number,
            "usage_percent_above": args.usage_percent_above,
            "estimated_bill": args.estimated_bill,
        },
    )

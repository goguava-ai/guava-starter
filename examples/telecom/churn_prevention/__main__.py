import argparse
import json
import logging
import os
from datetime import datetime, timezone

import guava
from guava import logging_utils

agent = guava.Agent(
    name="Jordan",
    organization="Nexus Mobile",
    purpose=(
        "to speak with valued Nexus Mobile subscribers who may be considering "
        "leaving, understand their concerns, and present personalized retention "
        "options to help them get the most out of their service"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(contact_full_name=call.get_variable("contact_name"))


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    if outcome == "unavailable":
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": "Jordan",
            "organization": "Nexus Mobile",
            "use_case": "churn_prevention",
            "contact_name": call.get_variable("contact_name"),
            "account_number": call.get_variable("account_number"),
            "status": "recipient_unavailable",
        }
        print(json.dumps(results, indent=2))
        logging.info("Recipient unavailable for churn prevention call.")
        call.hangup(
            final_instructions=(
                "The contact was not available. End the call politely without leaving "
                "sensitive account details in a voicemail."
            )
        )
    elif outcome == "available":
        contact_name = call.get_variable("contact_name")
        current_plan = call.get_variable("current_plan")
        tenure_months = call.get_variable("tenure_months")
        account_number = call.get_variable("account_number")
        call.set_task(
            "retention_flow",
            objective=(
                f"You are speaking with {contact_name}, a Nexus Mobile customer "
                f"on the {current_plan} plan who has been with us for "
                f"{tenure_months} months (account #{account_number}). "
                "Your goal is to understand why they may be considering cancellation, "
                "present relevant retention offers, and document their final decision. "
                "Be empathetic, listen carefully, and avoid being pushy."
            ),
            checklist=[
                guava.Say(
                    f"Hi {contact_name.split()[0]}, thank you so much for taking my call today. "
                    f"I'm reaching out because we truly value your loyalty over the past "
                    f"{tenure_months} months and want to make sure you're completely "
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
        )


@agent.on_task_complete("retention_flow")
def on_done(call: guava.Call) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": "Jordan",
        "organization": "Nexus Mobile",
        "use_case": "churn_prevention",
        "contact_name": call.get_variable("contact_name"),
        "account_number": call.get_variable("account_number"),
        "current_plan": call.get_variable("current_plan"),
        "tenure_months": call.get_variable("tenure_months"),
        "fields": {
            "primary_dissatisfaction_reason": call.get_field("primary_dissatisfaction_reason"),
            "competitor_offer_received": call.get_field("competitor_offer_received"),
            "alternative_plan_interest": call.get_field("alternative_plan_interest"),
            "retention_offer_accepted": call.get_field("retention_offer_accepted"),
            "cancellation_decision": call.get_field("cancellation_decision"),
        },
    }
    print(json.dumps(results, indent=2))
    logging.info("Churn prevention call results saved.")
    call.hangup(
        final_instructions=(
            "Thank the customer sincerely for their time and honesty. If they are staying, "
            "confirm any offer details and let them know a confirmation will be sent. "
            "If they are leaving, express genuine regret, remind them Nexus Mobile's door "
            "is always open, and wish them well."
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

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "contact_name": args.name,
            "account_number": args.account_number,
            "current_plan": args.current_plan,
            "tenure_months": args.tenure_months,
        },
    )

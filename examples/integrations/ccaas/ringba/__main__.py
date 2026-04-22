import guava
import os
import logging
from guava import logging_utils
import json
import argparse
import requests
from datetime import datetime, timezone


agent = guava.Agent(
    name="Alex",
    organization="Velocity Sales Group",
    purpose=(
        "to reach prospective customers, introduce Velocity's solutions, "
        "qualify their interest and budget, and capture key lead information"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(contact_full_name=call.get_variable("prospect_name"))


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    if outcome == "unavailable":
        call.hangup(
            final_instructions=(
                "We were unable to reach the prospect. Leave a brief, professional voicemail "
                "introducing Velocity Sales Group and asking them to call back at their "
                "convenience. Provide a callback number if available."
            )
        )
    elif outcome == "available":
        prospect_name = call.get_variable("prospect_name")
        call.set_task(
            "save_results",
            objective=(
                f"You've reached {prospect_name}. Introduce yourself and Velocity Sales Group, "
                "then qualify this lead by collecting their interest level, product preferences, "
                "budget range, and decision timeline. Be conversational and not pushy."
            ),
            checklist=[
                guava.Say(
                    f"Hi {prospect_name}, this is Alex calling from Velocity Sales Group. "
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
        )


@agent.on_task_complete("save_results")
def on_done(call: guava.Call) -> None:
    prospect_name = call.get_variable("prospect_name")
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": "Alex",
        "organization": "Velocity Sales Group",
        "use_case": "outbound_lead_qualification",
        "prospect_name": prospect_name,
        "fields": {
            "interest_level": call.get_field("interest_level"),
            "product_interest": call.get_field("product_interest"),
            "budget_range": call.get_field("budget_range"),
            "decision_timeline": call.get_field("decision_timeline"),
            "follow_up_preference": call.get_field("follow_up_preference"),
            "additional_notes": call.get_field("additional_notes"),
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
            "prospectName": prospect_name,
            "interestLevel": call.get_field("interest_level"),
            "productInterest": call.get_field("product_interest"),
            "budgetRange": call.get_field("budget_range"),
            "decisionTimeline": call.get_field("decision_timeline"),
            "followUpPreference": call.get_field("follow_up_preference"),
            "additionalNotes": call.get_field("additional_notes"),
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

    call.hangup(
        final_instructions=(
            "Thank the prospect for their time. Let them know a Velocity team member "
            "will follow up based on their preference. Wish them a great day."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
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

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "prospect_name": args.name,
        },
    )

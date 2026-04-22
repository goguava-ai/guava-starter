import argparse
import json
import logging
import os
from datetime import datetime, timezone

import guava
import requests
from guava import logging_utils

agent = guava.Agent(
    name="Jamie",
    organization="Pinnacle Commerce",
    purpose=(
        "to follow up with recent customers, collect their satisfaction feedback, "
        "and identify opportunities to improve the customer experience"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(contact_full_name=call.get_variable("customer_name"))


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    if outcome == "unavailable":
        call.hangup(
            final_instructions=(
                "We were unable to reach the customer. Leave a brief, friendly voicemail "
                "thanking them for their recent purchase from Pinnacle Commerce and inviting "
                "them to call back or reply to share their feedback."
            )
        )
    elif outcome == "available":
        customer_name = call.get_variable("customer_name")
        call.set_task(
            "save_results",
            objective=(
                f"You've reached {customer_name}. Thank them for their recent purchase "
                "from Pinnacle Commerce and conduct a brief satisfaction survey. Be friendly "
                "and respectful of their time."
            ),
            checklist=[
                guava.Say(
                    f"Hi {customer_name}, this is Jamie calling from Pinnacle Commerce. "
                    "Thank you for your recent purchase! I'd love to take just a couple of "
                    "minutes to hear about your experience."
                ),
                guava.Field(
                    key="overall_satisfaction",
                    description=(
                        "Ask the customer to rate their overall experience with Pinnacle Commerce "
                        "on a scale of 1-10, with 10 being the best. Capture the number."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="product_quality_rating",
                    description=(
                        "Ask how they would rate the quality of the product they received, "
                        "on a scale of 1-10. Capture the number."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="delivery_experience",
                    description=(
                        "Ask about their delivery experience — was the package on time, "
                        "in good condition, and as expected? Capture their feedback."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="would_recommend",
                    description=(
                        "Ask if they would recommend Pinnacle Commerce to a friend or colleague. "
                        "Capture yes, no, or maybe."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="improvement_suggestions",
                    description=(
                        "Ask if there is anything Pinnacle Commerce could do better. "
                        "Capture any suggestions or note if they have none."
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="permission_to_follow_up",
                    description=(
                        "Ask if they'd be open to being contacted for future promotions "
                        "or feedback requests. Capture yes or no."
                    ),
                    field_type="text",
                    required=True,
                ),
            ],
        )


@agent.on_task_complete("save_results")
def on_done(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": "Jamie",
        "organization": "Pinnacle Commerce",
        "use_case": "outbound_satisfaction_survey",
        "customer_name": customer_name,
        "fields": {
            "overall_satisfaction": call.get_field("overall_satisfaction"),
            "product_quality_rating": call.get_field("product_quality_rating"),
            "delivery_experience": call.get_field("delivery_experience"),
            "would_recommend": call.get_field("would_recommend"),
            "improvement_suggestions": call.get_field("improvement_suggestions"),
            "permission_to_follow_up": call.get_field("permission_to_follow_up"),
        },
    }
    print(json.dumps(results, indent=2))
    logging.info("Satisfaction survey results saved locally.")

    # Push contact and disposition to Five9
    try:
        api_url = os.environ["FIVE9_API_URL"]
        username = os.environ["FIVE9_USERNAME"]
        password = os.environ["FIVE9_PASSWORD"]
        campaign_name = os.environ["FIVE9_CAMPAIGN_NAME"]
        headers = {"Content-Type": "application/json"}

        contact_payload = {
            "campaignName": campaign_name,
            "contact": {
                "firstName": customer_name,
                "customFields": {
                    "overall_satisfaction": call.get_field("overall_satisfaction"),
                    "product_quality_rating": call.get_field("product_quality_rating"),
                    "delivery_experience": call.get_field("delivery_experience"),
                    "would_recommend": call.get_field("would_recommend"),
                    "improvement_suggestions": call.get_field("improvement_suggestions"),
                    "permission_to_follow_up": call.get_field("permission_to_follow_up"),
                },
            },
            "disposition": "survey_completed",
            "source": "guava_voice_agent",
        }
        resp = requests.post(
            f"{api_url}/orgs/{username}/contacts",
            headers=headers,
            auth=(username, password),
            json=contact_payload,
            timeout=10,
        )
        resp.raise_for_status()
        logging.info("Five9 contact and disposition pushed successfully.")
    except Exception as e:
        logging.error("Failed to push to Five9: %s", e)

    call.hangup(
        final_instructions=(
            "Thank the customer for taking the time to share their feedback. Let them "
            "know their input helps Pinnacle Commerce improve. Wish them a wonderful day."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound satisfaction survey call for Pinnacle Commerce."
    )
    parser.add_argument("phone", help="Customer phone number to call")
    parser.add_argument("--name", required=True, help="Full name of the customer")
    args = parser.parse_args()

    logging.info(
        "Initiating satisfaction survey call to %s (%s)",
        args.name,
        args.phone,
    )

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "customer_name": args.name,
        },
    )

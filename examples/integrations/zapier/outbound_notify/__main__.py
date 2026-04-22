import argparse
import logging
import os
from datetime import datetime, timezone

import guava
import requests
from guava import logging_utils

ZAPIER_WEBHOOK_URL = os.environ["ZAPIER_WEBHOOK_URL"]


def report_outcome(payload: dict) -> None:
    """POSTs the call outcome back to a Zapier Catch Hook for downstream logging."""
    resp = requests.post(ZAPIER_WEBHOOK_URL, json=payload, timeout=10)
    resp.raise_for_status()


agent = guava.Agent(
    name="Riley",
    organization="Clearpath",
    purpose=(
        "to deliver an important notification to Clearpath customers and confirm "
        "they received it"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    call.reach_person(contact_full_name=contact_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    contact_name = call.get_variable("contact_name")
    campaign_id = call.get_variable("campaign_id")
    message = call.get_variable("message")

    if outcome == "unavailable":
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "campaign_id": campaign_id,
            "contact_name": contact_name,
            "outcome": "unavailable",
            "questions": "",
            "call_status": "voicemail",
        }

        logging.info("Unable to reach %s — logging voicemail attempt.", contact_name)

        try:
            report_outcome(payload)
        except Exception as e:
            logging.error("Failed to report voicemail outcome to Zapier: %s", e)

        call.hangup(
            final_instructions=(
                f"Leave a brief, professional voicemail for {contact_name} from Clearpath. "
                "Summarize the key point of the notification message and ask them to call back "
                "or check their email for more details. Keep it under 30 seconds."
            )
        )
    elif outcome == "available":
        call.set_task(
            "log_outcome",
            objective=(
                f"Deliver an important notification to {contact_name} and confirm "
                "they received and understood it."
            ),
            checklist=[
                guava.Say(
                    f"Hi {contact_name}, this is Riley calling from Clearpath. "
                    "I have an important update I'd like to share with you."
                ),
                guava.Say(message),
                guava.Field(
                    key="acknowledged",
                    field_type="multiple_choice",
                    description=(
                        "Ask the contact to confirm they understood the message. "
                        "Capture their acknowledgment."
                    ),
                    choices=["yes, understood", "has questions", "wants to opt out"],
                    required=True,
                ),
                guava.Field(
                    key="questions",
                    field_type="text",
                    description=(
                        "If they have questions, ask them to describe their question or concern. "
                        "Answer what you can; note what requires follow-up."
                    ),
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("log_outcome")
def on_done(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    campaign_id = call.get_variable("campaign_id")
    acknowledged = call.get_field("acknowledged") or "yes, understood"
    questions = call.get_field("questions") or ""

    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "campaign_id": campaign_id,
        "contact_name": contact_name,
        "outcome": acknowledged,
        "questions": questions,
        "call_status": "completed",
    }

    logging.info(
        "Notification delivered to %s — acknowledged: %s", contact_name, acknowledged,
    )

    try:
        report_outcome(payload)
        logging.info("Outcome reported to Zapier for campaign %s.", campaign_id)
    except Exception as e:
        logging.error("Failed to report outcome to Zapier: %s", e)

    if acknowledged == "wants to opt out":
        call.hangup(
            final_instructions=(
                f"Acknowledge {contact_name}'s request to opt out. Let them know "
                "they've been removed from future notifications. Thank them for letting "
                "us know and wish them a good day."
            )
        )
    elif acknowledged == "has questions":
        call.hangup(
            final_instructions=(
                f"Thank {contact_name} for their question. Let them know a team member "
                "will follow up with a full answer within one business day. "
                "Apologize if the message caused any confusion and wish them a great day."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {contact_name} for their time. Let them know Clearpath is always "
                "available if they have questions. Wish them a great day."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound notification call triggered by a Zapier workflow."
    )
    parser.add_argument("phone", help="Contact's phone number (E.164, e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Full name of the contact to reach")
    parser.add_argument("--message", required=True, help="The notification message to deliver")
    parser.add_argument("--campaign-id", required=True, help="Campaign ID for tracking in Zapier")
    args = parser.parse_args()

    logging.info(
        "Initiating notification call to %s (%s) — campaign: %s",
        args.name, args.phone, args.campaign_id,
    )

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "contact_name": args.name,
            "message": args.message,
            "campaign_id": args.campaign_id,
        },
    )

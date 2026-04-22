import argparse
import json
import logging
import os
from datetime import datetime, timezone

import guava
from guava import logging_utils

agent = guava.Agent(
    name="Riley",
    organization="Pinnacle Realty Group",
    purpose=(
        "schedule and confirm property showings for interested buyers "
        "so they can tour homes at a time that works for them and their agent"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(contact_full_name=call.get_variable("contact_name"))


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    contact_name = call.get_variable("contact_name")
    property_address = call.get_variable("property_address")

    if outcome == "unavailable":
        logging.warning(
            "Could not reach %s for showing scheduling at %s.",
            contact_name,
            property_address,
        )
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "vertical": "real_estate",
            "use_case": "showing_scheduling",
            "contact_name": contact_name,
            "property_address": property_address,
            "status": "recipient_unavailable",
        }
        print(json.dumps(results, indent=2))
        call.hangup(
            final_instructions=(
                "Leave a brief, friendly voicemail introducing yourself as Riley from "
                "Pinnacle Realty Group. Mention that you are calling about scheduling "
                f"a showing for {property_address} and ask them to call back or "
                "check their email for a scheduling link. Keep the message under 30 seconds."
            )
        )
    elif outcome == "available":
        call.set_task(
            "showing_scheduling",
            objective=(
                f"You are calling {contact_name} on behalf of Pinnacle Realty Group "
                f"to schedule a showing for {property_address}. "
                "Be friendly and enthusiastic about the property. "
                "Work with the caller to find a date and time that fits their schedule, "
                "confirm any additional properties they may want to see, "
                "and verify their pre-approval status before wrapping up."
            ),
            checklist=[
                guava.Say(
                    f"Great news — we'd love to set up a showing for you at "
                    f"{property_address}. Let's find a time that works perfectly "
                    f"for your schedule."
                ),
                guava.Field(
                    key="showing_date_preference",
                    description=(
                        f"What date works best for you to tour {property_address}? "
                        "Please provide a specific date or a range of dates."
                    ),
                    field_type="date",
                    required=True,
                ),
                guava.Field(
                    key="showing_time_preference",
                    description=(
                        "What time of day works best for you — morning, afternoon, or evening? "
                        "If you have a specific time in mind, feel free to share it."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="additional_properties_interest",
                    description=(
                        "Are there any other properties you'd like to schedule showings for "
                        "during the same visit or around the same time?"
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="pre_approval_letter_ready",
                    description=(
                        "Have you received your mortgage pre-approval letter, or are you "
                        "planning to pay cash? Our agents will need this before making any offers."
                    ),
                    field_type="text",
                    required=True,
                ),
            ],
        )


@agent.on_task_complete("showing_scheduling")
def on_done(call: guava.Call) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "vertical": "real_estate",
        "use_case": "showing_scheduling",
        "contact_name": call.get_variable("contact_name"),
        "property_address": call.get_variable("property_address"),
        "fields": {
            "showing_date_preference": call.get_field("showing_date_preference"),
            "showing_time_preference": call.get_field("showing_time_preference"),
            "additional_properties_interest": call.get_field("additional_properties_interest"),
            "pre_approval_letter_ready": call.get_field("pre_approval_letter_ready"),
        },
    }
    print(json.dumps(results, indent=2))
    logging.info("Showing scheduling results captured: %s", results)
    call.hangup(
        final_instructions=(
            "Confirm the showing details back to the caller — the property address, "
            "date, and time. Let them know they'll receive a calendar confirmation "
            "and a reminder the day before. Thank them for their interest in "
            "Pinnacle Realty Group and wish them an exciting home search."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(description="Schedule a property showing outbound call.")
    parser.add_argument("phone", help="The buyer's phone number to call.")
    parser.add_argument("--name", required=True, help="Full name of the buyer to reach.")
    parser.add_argument(
        "--property-address",
        default="the property you inquired about",
        help="Address or description of the property to be shown.",
    )
    args = parser.parse_args()

    logging.info(
        "Initiating showing scheduling call to %s (%s) for property: %s",
        args.name,
        args.phone,
        args.property_address,
    )

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "contact_name": args.name,
            "property_address": args.property_address,
        },
    )

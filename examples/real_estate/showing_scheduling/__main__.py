import guava
import os
import logging
import json
import argparse
from datetime import datetime

logging.basicConfig(level=logging.INFO)


class ShowingSchedulingController(guava.CallController):
    def __init__(self, contact_name: str, property_address: str):
        super().__init__()
        self.contact_name = contact_name
        self.property_address = property_address
        self.set_persona(
            organization_name="Pinnacle Realty Group",
            agent_name="Riley",
            agent_purpose=(
                "schedule and confirm property showings for interested buyers "
                "so they can tour homes at a time that works for them and their agent"
            ),
        )
        self.reach_person(
            contact_full_name=self.contact_name,
            on_success=self.start_scheduling,
            on_failure=self.recipient_unavailable,
        )

    def start_scheduling(self):
        self.set_task(
            objective=(
                f"You are calling {self.contact_name} on behalf of Pinnacle Realty Group "
                f"to schedule a showing for {self.property_address}. "
                "Be friendly and enthusiastic about the property. "
                "Work with the caller to find a date and time that fits their schedule, "
                "confirm any additional properties they may want to see, "
                "and verify their pre-approval status before wrapping up."
            ),
            checklist=[
                guava.Say(
                    f"Great news — we'd love to set up a showing for you at "
                    f"{self.property_address}. Let's find a time that works perfectly "
                    f"for your schedule."
                ),
                guava.Field(
                    key="showing_date_preference",
                    description=(
                        f"What date works best for you to tour {self.property_address}? "
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
            on_complete=self.save_results,
        )

    def save_results(self):
        results = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "vertical": "real_estate",
            "use_case": "showing_scheduling",
            "contact_name": self.contact_name,
            "property_address": self.property_address,
            "fields": {
                "showing_date_preference": self.get_field("showing_date_preference"),
                "showing_time_preference": self.get_field("showing_time_preference"),
                "additional_properties_interest": self.get_field("additional_properties_interest"),
                "pre_approval_letter_ready": self.get_field("pre_approval_letter_ready"),
            },
        }
        print(json.dumps(results, indent=2))
        logging.info("Showing scheduling results captured: %s", results)
        self.hangup(
            final_instructions=(
                "Confirm the showing details back to the caller — the property address, "
                "date, and time. Let them know they'll receive a calendar confirmation "
                "and a reminder the day before. Thank them for their interest in "
                "Pinnacle Realty Group and wish them an exciting home search."
            )
        )

    def recipient_unavailable(self):
        logging.warning(
            "Could not reach %s for showing scheduling at %s.",
            self.contact_name,
            self.property_address,
        )
        results = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "vertical": "real_estate",
            "use_case": "showing_scheduling",
            "contact_name": self.contact_name,
            "property_address": self.property_address,
            "status": "recipient_unavailable",
        }
        print(json.dumps(results, indent=2))
        self.hangup(
            final_instructions=(
                "Leave a brief, friendly voicemail introducing yourself as Riley from "
                "Pinnacle Realty Group. Mention that you are calling about scheduling "
                f"a showing for {self.property_address} and ask them to call back or "
                "check their email for a scheduling link. Keep the message under 30 seconds."
            )
        )


if __name__ == "__main__":
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

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=ShowingSchedulingController(
            contact_name=args.name,
            property_address=args.property_address,
        ),
    )

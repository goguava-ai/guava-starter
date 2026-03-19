import guava
import os
import logging
import json
import argparse
from datetime import datetime

logging.basicConfig(level=logging.INFO)


class AlumniFundraisingController(guava.CallController):
    def __init__(self, name, graduation_year, major):
        super().__init__()
        self.name = name
        self.graduation_year = graduation_year
        self.major = major
        self.set_persona(
            organization_name="Westfield University - Alumni Relations",
            agent_name="Morgan",
            agent_purpose=(
                "engage alumni in meaningful conversation about giving back to the university "
                "and capture gift pledges and preferences to support future students"
            ),
        )
        self.reach_person(
            contact_full_name=self.name,
            on_success=self.begin_fundraising_call,
            on_failure=self.recipient_unavailable,
        )

    def begin_fundraising_call(self):
        self.set_task(
            objective=(
                f"You are calling {self.name}, a Westfield University alumnus who graduated in "
                f"{self.graduation_year} from {self.major}. "
                "Your goal is to reconnect warmly, share the impact of alumni giving, and invite them "
                "to make a gift. Capture whether they are open to giving, and if so, gather the gift "
                "amount, gift type, any designation preference, and a pledge date. "
                "If they are not interested, capture the reason respectfully. "
                "Be conversational, grateful, and never pushy."
            ),
            checklist=[
                guava.Say(
                    f"Hello {self.name}! This is Morgan calling from Westfield University Alumni Relations. "
                    f"I hope you're doing well. I'm reaching out to connect with fellow Westfield alumni "
                    f"like yourself — class of {self.graduation_year} from {self.major} — and share some "
                    "exciting things happening on campus. Do you have just a few minutes to chat?"
                ),
                guava.Field(
                    key="open_to_giving",
                    description="Whether the alumnus is open to making a gift or pledge to the university",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="gift_amount",
                    description="The dollar amount the alumnus would like to give or pledge",
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="gift_type",
                    description=(
                        "The type of gift the alumnus prefers. "
                        "Options are: one_time, monthly, or annual"
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="designation_preference",
                    description=(
                        "Where the alumnus would like their gift directed, such as: "
                        "scholarship, athletics, general_fund, or another area of their choosing"
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="pledge_date",
                    description="The date by which the alumnus intends to fulfill their pledge or make a payment",
                    field_type="date",
                    required=False,
                ),
                guava.Field(
                    key="decline_reason",
                    description="If the alumnus is not open to giving, the reason they provided",
                    field_type="text",
                    required=False,
                ),
            ],
            on_complete=self.save_results,
        )

    def save_results(self):
        results = {
            "timestamp": datetime.now().isoformat(),
            "alumni_name": self.name,
            "graduation_year": self.graduation_year,
            "major": self.major,
            "fields": {
                "open_to_giving": self.get_field("open_to_giving"),
                "gift_amount": self.get_field("gift_amount"),
                "gift_type": self.get_field("gift_type"),
                "designation_preference": self.get_field("designation_preference"),
                "pledge_date": self.get_field("pledge_date"),
                "decline_reason": self.get_field("decline_reason"),
            },
        }
        print(json.dumps(results, indent=2))
        self.hangup(
            final_instructions=(
                f"Thank {self.name} sincerely for their time and, if they made a pledge, for their "
                "generous support of Westfield University. Let them know they will receive a follow-up "
                "by email. If they were not interested, thank them warmly and invite them to stay "
                "connected with the alumni community. Close the call on a positive note."
            )
        )

    def recipient_unavailable(self):
        logging.info(
            "Could not reach alumnus %s (class of %s) for fundraising call.",
            self.name,
            self.graduation_year,
        )
        results = {
            "timestamp": datetime.now().isoformat(),
            "alumni_name": self.name,
            "graduation_year": self.graduation_year,
            "major": self.major,
            "outcome": "recipient_unavailable",
        }
        print(json.dumps(results, indent=2))
        self.hangup(
            final_instructions=(
                "The alumnus could not be reached. End the call politely."
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Alumni fundraising call to collect gift pledges and preferences"
    )
    parser.add_argument("phone", help="Phone number to call (e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Full name of the alumnus")
    parser.add_argument(
        "--graduation-year",
        required=True,
        help="Year the alumnus graduated (e.g. '2015')",
    )
    parser.add_argument(
        "--major",
        default="your program",
        help="Alumnus's field of study (default: 'your program')",
    )
    args = parser.parse_args()

    guava.Client().create_outbound(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        call_controller=AlumniFundraisingController(
            name=args.name,
            graduation_year=args.graduation_year,
            major=args.major,
        ),
    )

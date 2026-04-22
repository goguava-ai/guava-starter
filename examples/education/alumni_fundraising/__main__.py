import argparse
import json
import logging
import os
from datetime import datetime

import guava
from guava import logging_utils

agent = guava.Agent(
    name="Morgan",
    organization="Westfield University - Alumni Relations",
    purpose=(
        "engage alumni in meaningful conversation about giving back to the university "
        "and capture gift pledges and preferences to support future students"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(contact_full_name=call.get_variable("name"))


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    if outcome == "unavailable":
        logging.info(
            "Could not reach alumnus %s (class of %s) for fundraising call.",
            call.get_variable("name"),
            call.get_variable("graduation_year"),
        )
        results = {
            "timestamp": datetime.now().isoformat(),
            "alumni_name": call.get_variable("name"),
            "graduation_year": call.get_variable("graduation_year"),
            "major": call.get_variable("major"),
            "outcome": "recipient_unavailable",
        }
        print(json.dumps(results, indent=2))
        call.hangup(
            final_instructions=(
                "The alumnus could not be reached. End the call politely."
            )
        )
    elif outcome == "available":
        call.set_task(
            "outreach",
            objective=(
                f"You are calling {call.get_variable('name')}, a Westfield University alumnus who graduated in "
                f"{call.get_variable('graduation_year')} from {call.get_variable('major')}. "
                "Your goal is to reconnect warmly, share the impact of alumni giving, and invite them "
                "to make a gift. Capture whether they are open to giving, and if so, gather the gift "
                "amount, gift type, any designation preference, and a pledge date. "
                "If they are not interested, capture the reason respectfully. "
                "Be conversational, grateful, and never pushy."
            ),
            checklist=[
                guava.Say(
                    f"Hello {call.get_variable('name')}! This is Morgan calling from Westfield University Alumni Relations. "
                    f"I hope you're doing well. I'm reaching out to connect with fellow Westfield alumni "
                    f"like yourself — class of {call.get_variable('graduation_year')} from {call.get_variable('major')} — and share some "
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
        )


@agent.on_task_complete("outreach")
def on_done(call: guava.Call) -> None:
    results = {
        "timestamp": datetime.now().isoformat(),
        "alumni_name": call.get_variable("name"),
        "graduation_year": call.get_variable("graduation_year"),
        "major": call.get_variable("major"),
        "fields": {
            "open_to_giving": call.get_field("open_to_giving"),
            "gift_amount": call.get_field("gift_amount"),
            "gift_type": call.get_field("gift_type"),
            "designation_preference": call.get_field("designation_preference"),
            "pledge_date": call.get_field("pledge_date"),
            "decline_reason": call.get_field("decline_reason"),
        },
    }
    print(json.dumps(results, indent=2))
    call.hangup(
        final_instructions=(
            f"Thank {call.get_variable('name')} sincerely for their time and, if they made a pledge, for their "
            "generous support of Westfield University. Let them know they will receive a follow-up "
            "by email. If they were not interested, thank them warmly and invite them to stay "
            "connected with the alumni community. Close the call on a positive note."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
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

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "name": args.name,
            "graduation_year": args.graduation_year,
            "major": args.major,
        },
    )

import argparse
import json
import logging
import os
from datetime import datetime, timezone

import guava
from guava import logging_utils

agent = guava.Agent(
    name="Riley",
    organization="Hargrove & Associates Law Firm",
    purpose=(
        "to coordinate scheduling for a legal proceeding and confirm the "
        "availability, preferred logistics, and contact details of the party "
        "being reached"
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
            "call_type": "outbound_scheduling",
            "status": "recipient_unavailable",
            "meta": {
                "contact_name": call.get_variable("contact_name"),
                "matter_number": call.get_variable("matter_number"),
                "event_type": call.get_variable("event_type"),
                "proposed_date": call.get_variable("proposed_date"),
            },
        }
        print(json.dumps(results, indent=2))
        logging.info("Recipient unavailable for scheduling call.")
        call.hangup(
            final_instructions=(
                "Leave a brief, professional voicemail identifying yourself as Riley "
                "calling from Hargrove and Associates Law Firm. State that you are "
                f"calling regarding the scheduling of an upcoming {call.get_variable('event_type')} "
                f"for matter number {call.get_variable('matter_number')} and that you would appreciate "
                "a call back at their earliest convenience. Provide the firm's main "
                "number and say goodbye."
            )
        )
    elif outcome == "available":
        call.set_task(
            "scheduling",
            objective=(
                f"Confirm scheduling details for an upcoming {call.get_variable('event_type')} related "
                f"to matter number {call.get_variable('matter_number')}. The firm has proposed "
                f"{call.get_variable('proposed_date')} as a potential date. Verify the party's "
                "availability, collect their preferences, and obtain a confirmation "
                "email address. Remain professional and courteous throughout."
            ),
            checklist=[
                guava.Say(
                    f"Good day. I am calling on behalf of Hargrove and Associates Law "
                    f"Firm regarding the scheduling of an upcoming {call.get_variable('event_type')} "
                    f"for matter number {call.get_variable('matter_number')}. The firm has proposed "
                    f"{call.get_variable('proposed_date')} as a potential date, and I would like to "
                    "confirm your availability and preferred arrangements."
                ),
                guava.Field(
                    key="availability_confirmed",
                    description=(
                        f"Whether the party is available on or around the proposed date "
                        f"of {call.get_variable('proposed_date')} for the {call.get_variable('event_type')}"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="preferred_date",
                    description=(
                        f"The party's preferred date for the {call.get_variable('event_type')}, "
                        f"if different from the proposed date of {call.get_variable('proposed_date')}"
                    ),
                    field_type="date",
                    required=True,
                ),
                guava.Field(
                    key="preferred_time",
                    description=(
                        f"The party's preferred time of day for the {call.get_variable('event_type')}, "
                        "such as morning, afternoon, or a specific hour"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="location_preference",
                    description=(
                        f"How the party would prefer to participate in the "
                        f"{call.get_variable('event_type')}: in person, by video conference, or by phone"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="special_accommodations",
                    description=(
                        "Any special accommodations or requirements the party needs, "
                        "such as accessibility needs, an interpreter, or technical "
                        "requirements for video participation"
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="confirmation_email",
                    description=(
                        "The email address where the party would like to receive the "
                        "formal scheduling confirmation and any related documents"
                    ),
                    field_type="text",
                    required=True,
                ),
            ],
        )


@agent.on_task_complete("scheduling")
def on_done(call: guava.Call) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "call_type": "outbound_scheduling",
        "meta": {
            "contact_name": call.get_variable("contact_name"),
            "matter_number": call.get_variable("matter_number"),
            "event_type": call.get_variable("event_type"),
            "proposed_date": call.get_variable("proposed_date"),
        },
        "fields": {
            "availability_confirmed": call.get_field("availability_confirmed"),
            "preferred_date": call.get_field("preferred_date"),
            "preferred_time": call.get_field("preferred_time"),
            "location_preference": call.get_field("location_preference"),
            "special_accommodations": call.get_field("special_accommodations"),
            "confirmation_email": call.get_field("confirmation_email"),
        },
    }
    print(json.dumps(results, indent=2))
    logging.info("Scheduling results saved.")
    call.hangup(
        final_instructions=(
            "Thank the party by name for their time and cooperation. Confirm that "
            "the scheduling details have been recorded and that they will receive a "
            "formal confirmation at the email address they provided. Let them know "
            "that if anything changes or they have questions, they are welcome to "
            "contact Hargrove and Associates directly. Say goodbye professionally."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound scheduling coordination call — Hargrove & Associates"
    )
    parser.add_argument("phone", help="Recipient phone number to dial")
    parser.add_argument("--name", required=True, help="Full name of the contact")
    parser.add_argument("--matter-number", required=True, help="Matter or case number")
    parser.add_argument(
        "--event-type",
        default="deposition",
        help="Type of legal event being scheduled (default: deposition)",
    )
    parser.add_argument(
        "--proposed-date", required=True, help="Proposed date for the event"
    )
    args = parser.parse_args()

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "contact_name": args.name,
            "matter_number": args.matter_number,
            "event_type": args.event_type,
            "proposed_date": args.proposed_date,
        },
    )

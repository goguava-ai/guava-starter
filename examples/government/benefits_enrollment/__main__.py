import argparse
import json
import logging
import os
from datetime import datetime, timezone

import guava
from guava import logging_utils

agent = guava.Agent(
    name="Jordan",
    organization="City of Springfield - Community Services",
    purpose=(
        "inform eligible residents about the benefits program and guide them "
        "through initial enrollment questions"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(contact_full_name=call.get_variable("resident_name"))


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    if outcome == "unavailable":
        logging.info(
            "Resident %s was unavailable for benefits enrollment call regarding %s.",
            call.get_variable("resident_name"),
            call.get_variable("program_name"),
        )
    elif outcome == "available":
        resident_name = call.get_variable("resident_name")
        program_name = call.get_variable("program_name")
        eligibility_reason = call.get_variable("eligibility_reason")
        call.set_task(
            "enrollment",
            objective=(
                f"You are calling on behalf of the City of Springfield Community Services "
                f"department to inform {resident_name} that they may be eligible for "
                f"{program_name}. The reason they may qualify is: {eligibility_reason}. "
                "Briefly explain the program, then walk through the enrollment questions in a "
                "helpful and neutral public-service tone. Let the resident know their answers "
                "will be used only to determine eligibility and enrollment preferences."
            ),
            checklist=[
                guava.Say(
                    f"Hello, I'm calling from the City of Springfield Community Services "
                    f"department. We're reaching out because you may be eligible for "
                    f"{program_name}. The reason you may qualify is: {eligibility_reason}. "
                    "I have a few quick questions to help us understand your situation and "
                    "enrollment preferences. This should only take a couple of minutes."
                ),
                guava.Field(
                    key="interested_in_enrolling",
                    description="Ask whether the resident is interested in learning more about or enrolling in the program.",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="household_size",
                    description="Ask for the total number of people currently living in the resident's household.",
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="annual_household_income_range",
                    description=(
                        "Ask the resident to describe their approximate annual household income range "
                        "(e.g., under $20,000, $20,000–$40,000, $40,000–$60,000, over $60,000)."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="currently_receiving_benefits",
                    description=(
                        "Ask whether the resident is currently receiving any government assistance "
                        "or benefits programs, and if so, which ones."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="program_questions",
                    description=(
                        "Ask if the resident has any questions about the program before proceeding."
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="preferred_enrollment_method",
                    description=(
                        "Ask how the resident would prefer to complete enrollment: "
                        "online, by phone, or in person."
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="best_callback_time",
                    description=(
                        "Ask if there is a preferred time for a follow-up call or appointment, "
                        "if one is needed."
                    ),
                    field_type="text",
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("enrollment")
def on_done(call: guava.Call) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "resident_name": call.get_variable("resident_name"),
        "program_name": call.get_variable("program_name"),
        "eligibility_reason": call.get_variable("eligibility_reason"),
        "fields": {
            "interested_in_enrolling": call.get_field("interested_in_enrolling"),
            "household_size": call.get_field("household_size"),
            "annual_household_income_range": call.get_field("annual_household_income_range"),
            "currently_receiving_benefits": call.get_field("currently_receiving_benefits"),
            "program_questions": call.get_field("program_questions"),
            "preferred_enrollment_method": call.get_field("preferred_enrollment_method"),
            "best_callback_time": call.get_field("best_callback_time"),
        },
    }
    print(json.dumps(results, indent=2))
    call.hangup(
        final_instructions=(
            "Thank the resident for their time. Let them know that a Community Services "
            "representative will follow up with next steps based on their enrollment preference. "
            "Remind them they can also call the City of Springfield Community Services office "
            "directly with any questions. Wish them a good day and end the call politely."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound benefits enrollment call for City of Springfield Community Services."
    )
    parser.add_argument("phone", help="Resident phone number to call (E.164 format).")
    parser.add_argument("--name", required=True, help="Full name of the resident.")
    parser.add_argument(
        "--program-name",
        required=True,
        help='Name of the benefits program (e.g., "the Utility Assistance Program").',
    )
    parser.add_argument(
        "--eligibility-reason",
        required=True,
        help="Brief explanation of why the resident may qualify for the program.",
    )
    args = parser.parse_args()

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "resident_name": args.name,
            "program_name": args.program_name,
            "eligibility_reason": args.eligibility_reason,
        },
    )

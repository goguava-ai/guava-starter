import guava
import os
import logging
from guava import logging_utils
import json
import argparse
from datetime import datetime



agent = guava.Agent(
    name="Jordan",
    organization="Westfield University - Enrollment Services",
    purpose=(
        "follow up with students who have incomplete enrollment paperwork "
        "and help them understand what is missing and how to submit it"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(contact_full_name=call.get_variable("name"))


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    if outcome == "unavailable":
        logging.info(
            "Could not reach %s for enrollment follow-up (student ID: %s).",
            call.get_variable("name"),
            call.get_variable("student_id"),
        )
        results = {
            "timestamp": datetime.now().isoformat(),
            "student_name": call.get_variable("name"),
            "student_id": call.get_variable("student_id"),
            "missing_items": call.get_variable("missing_items"),
            "term": call.get_variable("term"),
            "outcome": "recipient_unavailable",
        }
        print(json.dumps(results, indent=2))
        call.hangup(
            final_instructions=(
                "The student could not be reached. End the call politely."
            )
        )
    elif outcome == "available":
        call.set_task(
            "followup",
            objective=(
                f"You are following up with {call.get_variable('name')} (student ID: {call.get_variable('student_id')}) "
                f"regarding incomplete enrollment paperwork for the {call.get_variable('term')} term. "
                f"The following items are still missing or incomplete: {call.get_variable('missing_items')}. "
                "Inform the student clearly, confirm they understand what is needed, "
                "find out how they plan to submit the missing items and by when, "
                "confirm they are still planning to start the upcoming term, "
                "and address any questions they may have about the enrollment process."
            ),
            checklist=[
                guava.Say(
                    f"Hello {call.get_variable('name')}, I'm calling from Westfield University Enrollment Services "
                    f"regarding your enrollment for {call.get_variable('term')}. We show that your file is missing "
                    f"the following: {call.get_variable('missing_items')}. We want to make sure we get everything "
                    "sorted out so your enrollment is complete."
                ),
                guava.Field(
                    key="missing_info_acknowledged",
                    description="Confirm the student acknowledges what information or documents are missing from their enrollment file",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="info_submission_method",
                    description=(
                        "How the student plans to submit the missing information or documents. "
                        "Options are: online_portal, email, or in_person"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="submission_date_commitment",
                    description="The date by which the student commits to submitting the missing items",
                    field_type="date",
                    required=True,
                ),
                guava.Field(
                    key="term_start_confirmed",
                    description=f"Whether the student confirms they are still planning to enroll and start the {call.get_variable('term')} term",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="questions_about_enrollment",
                    description="Any questions or concerns the student has about the enrollment process",
                    field_type="text",
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("followup")
def on_done(call: guava.Call) -> None:
    results = {
        "timestamp": datetime.now().isoformat(),
        "student_name": call.get_variable("name"),
        "student_id": call.get_variable("student_id"),
        "missing_items": call.get_variable("missing_items"),
        "term": call.get_variable("term"),
        "fields": {
            "missing_info_acknowledged": call.get_field("missing_info_acknowledged"),
            "info_submission_method": call.get_field("info_submission_method"),
            "submission_date_commitment": call.get_field("submission_date_commitment"),
            "term_start_confirmed": call.get_field("term_start_confirmed"),
            "questions_about_enrollment": call.get_field("questions_about_enrollment"),
        },
    }
    print(json.dumps(results, indent=2))
    call.hangup(
        final_instructions=(
            f"Thank {call.get_variable('name')} for their time. Let them know that Enrollment Services "
            "is happy to help if they have any further questions and wish them a great start "
            f"to the {call.get_variable('term')} term. Say goodbye warmly."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Enrollment follow-up call for students with incomplete paperwork"
    )
    parser.add_argument("phone", help="Phone number to call (e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Full name of the student")
    parser.add_argument("--student-id", required=True, help="Student ID number")
    parser.add_argument(
        "--missing-items",
        required=True,
        help="Description of what enrollment items are incomplete",
    )
    parser.add_argument(
        "--term",
        required=True,
        help="Enrollment term (e.g. 'Fall 2026')",
    )
    args = parser.parse_args()

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "name": args.name,
            "student_id": args.student_id,
            "missing_items": args.missing_items,
            "term": args.term,
        },
    )

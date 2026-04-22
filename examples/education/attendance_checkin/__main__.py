import guava
import os
import logging
from guava import logging_utils
import json
import argparse
from datetime import datetime



agent = guava.Agent(
    name="Casey",
    organization="Westfield Elementary School - Attendance Office",
    purpose=(
        "contact parents and guardians when a student has an unexcused absence "
        "to collect a reason and ensure the family is aware"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(contact_full_name=call.get_variable("parent_name"))


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    if outcome == "unavailable":
        logging.info(
            "Could not reach parent/guardian %s for attendance check-in (student: %s, date: %s).",
            call.get_variable("parent_name"),
            call.get_variable("student_name"),
            call.get_variable("absence_date"),
        )
        results = {
            "timestamp": datetime.now().isoformat(),
            "parent_name": call.get_variable("parent_name"),
            "student_name": call.get_variable("student_name"),
            "absence_date": call.get_variable("absence_date"),
            "periods_missed": call.get_variable("periods_missed"),
            "outcome": "recipient_unavailable",
        }
        print(json.dumps(results, indent=2))
        call.hangup(
            final_instructions=(
                "The parent or guardian could not be reached. End the call politely."
            )
        )
    elif outcome == "available":
        call.set_task(
            "intake",
            objective=(
                f"You are calling {call.get_variable('parent_name')}, the parent or guardian of {call.get_variable('student_name')}, "
                f"because {call.get_variable('student_name')} has an unexcused absence on {call.get_variable('absence_date')} "
                f"for {call.get_variable('periods_missed')}. "
                "Your goal is to collect the reason for the absence, find out if the student is expected "
                "to return, determine whether a doctor's note will be provided, confirm the parent is aware "
                "of the absence, and capture any message they would like passed along to the teacher."
            ),
            checklist=[
                guava.Say(
                    f"Hello {call.get_variable('parent_name')}, this is Casey calling from Westfield Elementary School's "
                    f"Attendance Office. I'm reaching out today because {call.get_variable('student_name')} was marked "
                    f"absent on {call.get_variable('absence_date')} for {call.get_variable('periods_missed')}, and we don't currently "
                    "have an excuse on file. I just wanted to check in and make sure everything is okay."
                ),
                guava.Field(
                    key="absence_reason",
                    description=(
                        f"The reason for {call.get_variable('student_name')}'s absence. "
                        "Options are: illness, family_emergency, appointment, other, or unknown"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="expected_return_date",
                    description=f"The date on which {call.get_variable('student_name')} is expected to return to school",
                    field_type="date",
                    required=False,
                ),
                guava.Field(
                    key="doctor_note_available",
                    description=f"Whether a doctor's note or official documentation will be provided for the absence",
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="parent_aware_of_absence",
                    description=f"Confirmation that {call.get_variable('parent_name')} is aware of and can account for {call.get_variable('student_name')}'s absence",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="additional_message_for_teacher",
                    description="Any message the parent or guardian would like passed along to the teacher or school",
                    field_type="text",
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("intake")
def on_done(call: guava.Call) -> None:
    results = {
        "timestamp": datetime.now().isoformat(),
        "parent_name": call.get_variable("parent_name"),
        "student_name": call.get_variable("student_name"),
        "absence_date": call.get_variable("absence_date"),
        "periods_missed": call.get_variable("periods_missed"),
        "fields": {
            "absence_reason": call.get_field("absence_reason"),
            "expected_return_date": call.get_field("expected_return_date"),
            "doctor_note_available": call.get_field("doctor_note_available"),
            "parent_aware_of_absence": call.get_field("parent_aware_of_absence"),
            "additional_message_for_teacher": call.get_field("additional_message_for_teacher"),
        },
    }
    print(json.dumps(results, indent=2))
    call.hangup(
        final_instructions=(
            f"Thank {call.get_variable('parent_name')} for taking the time to speak with the school. "
            f"Let them know the absence will be updated in the system and wish {call.get_variable('student_name')} "
            "a speedy recovery or a good rest of the day. End the call warmly."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Attendance check-in call to parent or guardian for unexcused student absence"
    )
    parser.add_argument("phone", help="Phone number to call (e.g. +15551234567)")
    parser.add_argument("--parent-name", required=True, help="Full name of the parent or guardian")
    parser.add_argument("--student-name", required=True, help="Full name of the student")
    parser.add_argument(
        "--date",
        required=True,
        dest="absence_date",
        help="Date of the absence (e.g. 'February 25, 2026')",
    )
    parser.add_argument(
        "--periods-missed",
        default="the full day",
        help="Which periods or portion of the day were missed (default: 'the full day')",
    )
    args = parser.parse_args()

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "parent_name": args.parent_name,
            "student_name": args.student_name,
            "absence_date": args.absence_date,
            "periods_missed": args.periods_missed,
        },
    )

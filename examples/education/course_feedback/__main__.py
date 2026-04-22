import argparse
import json
import logging
import os
from datetime import datetime

import guava
from guava import logging_utils

agent = guava.Agent(
    name="Sam",
    organization="Westfield University - Academic Affairs",
    purpose=(
        "gather structured post-term feedback from students on their course "
        "and instructor experience to help improve academic quality"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(contact_full_name=call.get_variable("name"))


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    if outcome == "unavailable":
        logging.info(
            "Could not reach %s for course feedback on '%s' (%s).",
            call.get_variable("name"),
            call.get_variable("course_name"),
            call.get_variable("term"),
        )
        results = {
            "timestamp": datetime.now().isoformat(),
            "student_name": call.get_variable("name"),
            "course_name": call.get_variable("course_name"),
            "instructor_name": call.get_variable("instructor_name"),
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
            "survey",
            objective=(
                f"You are calling {call.get_variable('name')} to collect feedback on the course "
                f"'{call.get_variable('course_name')}' taught by {call.get_variable('instructor_name')} during the {call.get_variable('term')} term. "
                "Gather numeric ratings on a scale of 1 to 5 for overall course quality, the instructor, "
                "and course difficulty. Also capture open-ended responses about what the student found "
                "most valuable, what could be improved, and whether they would recommend the course "
                "to other students. Be friendly and assure the student their feedback is anonymous "
                "and genuinely valued."
            ),
            checklist=[
                guava.Say(
                    f"Hi {call.get_variable('name')}, this is Sam from Westfield University Academic Affairs. "
                    f"Now that the {call.get_variable('term')} term has wrapped up, we're reaching out to students "
                    f"to collect feedback on their courses. I'd love to get your thoughts on "
                    f"'{call.get_variable('course_name')}' with {call.get_variable('instructor_name')} — it should only take a couple "
                    "of minutes, and your responses are kept confidential."
                ),
                guava.Field(
                    key="course_overall_rating",
                    description=(
                        f"The student's overall rating of '{call.get_variable('course_name')}' on a scale of 1 to 5, "
                        "where 1 is poor and 5 is excellent"
                    ),
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="instructor_rating",
                    description=(
                        f"The student's rating of instructor {call.get_variable('instructor_name')} on a scale of 1 to 5, "
                        "where 1 is poor and 5 is excellent"
                    ),
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="course_difficulty_rating",
                    description=(
                        f"The student's rating of how difficult they found '{call.get_variable('course_name')}' "
                        "on a scale of 1 to 5, where 1 is very easy and 5 is very difficult"
                    ),
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="most_valuable_aspect",
                    description=f"The aspect of '{call.get_variable('course_name')}' the student found most valuable or memorable",
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="suggested_improvements",
                    description=f"Any improvements or changes the student would suggest for '{call.get_variable('course_name')}'",
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="would_recommend_course",
                    description=f"Whether the student would recommend '{call.get_variable('course_name')}' to other students, and any context they provide",
                    field_type="text",
                    required=True,
                ),
            ],
        )


@agent.on_task_complete("survey")
def on_done(call: guava.Call) -> None:
    results = {
        "timestamp": datetime.now().isoformat(),
        "student_name": call.get_variable("name"),
        "course_name": call.get_variable("course_name"),
        "instructor_name": call.get_variable("instructor_name"),
        "term": call.get_variable("term"),
        "fields": {
            "course_overall_rating": call.get_field("course_overall_rating"),
            "instructor_rating": call.get_field("instructor_rating"),
            "course_difficulty_rating": call.get_field("course_difficulty_rating"),
            "most_valuable_aspect": call.get_field("most_valuable_aspect"),
            "suggested_improvements": call.get_field("suggested_improvements"),
            "would_recommend_course": call.get_field("would_recommend_course"),
        },
    }
    print(json.dumps(results, indent=2))
    call.hangup(
        final_instructions=(
            f"Thank {call.get_variable('name')} sincerely for taking the time to share their feedback. "
            "Let them know their input genuinely helps Westfield University improve the "
            "student experience. Wish them the best for the upcoming term and say goodbye warmly."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Post-term course feedback call to collect student ratings and comments"
    )
    parser.add_argument("phone", help="Phone number to call (e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Full name of the student")
    parser.add_argument("--course-name", required=True, help="Name of the course being evaluated")
    parser.add_argument(
        "--instructor-name",
        required=True,
        help="Full name of the course instructor",
    )
    parser.add_argument(
        "--term",
        required=True,
        help="Academic term being evaluated (e.g. 'Fall 2025')",
    )
    args = parser.parse_args()

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "name": args.name,
            "course_name": args.course_name,
            "instructor_name": args.instructor_name,
            "term": args.term,
        },
    )

# SDK conformance: guava-sdk 0.35.0 (2026-07-21)
import argparse
import json
import logging
import os
from datetime import datetime, timezone

import guava
from guava import logging_utils
from guava.helpers.llm import IntentRecognizer

agent = guava.Agent(
    name="Sam",
    organization="Westfield University — Academic Affairs",
    purpose=(
        "gather structured post-term feedback from students on their course "
        "and instructor experience to help improve academic quality"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
    "speak_to_someone": "The caller wants to speak to a real person in Academic Affairs or an advisor",
})


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(
        contact_full_name=call.get_variable("name"),
        voicemail_message=(
            f"Hi, this is Sam from Westfield University Academic Affairs "
            f"calling for {call.get_variable('name')}. We're reaching out to "
            f"collect feedback on your recent coursework. Please call us back "
            f"at your convenience. Thank you!"
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    student_name = call.get_variable("name")
    course_name = call.get_variable("course_name")
    instructor_name = call.get_variable("instructor_name")
    term = call.get_variable("term")

    if outcome == "available":
        call.set_task(
            "survey",
            objective=(
                f"You are calling {student_name} to collect feedback on the course "
                f"'{course_name}' taught by {instructor_name} during the {term} term. "
                f"Gather numeric ratings on a scale of 1 to 5 for overall course "
                f"quality, the instructor, and course difficulty. Be friendly and "
                f"assure the student their feedback is confidential and genuinely valued."
            ),
            checklist=[
                guava.Say(
                    f"Now that the {term} term has wrapped up, we're reaching "
                    f"out to collect feedback on your courses. I'd love to get "
                    f"your thoughts on '{course_name}' with {instructor_name} "
                    f"— it should only take a couple of minutes, and your "
                    f"responses are kept confidential."
                ),
                guava.Field(
                    key="course_overall_rating",
                    description=(
                        f"The student's overall rating of '{course_name}' on a "
                        f"scale of 1 to 5, where 1 is poor and 5 is excellent"
                    ),
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="instructor_rating",
                    description=(
                        f"The student's rating of instructor {instructor_name} on "
                        f"a scale of 1 to 5, where 1 is poor and 5 is excellent"
                    ),
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="course_difficulty_rating",
                    description=(
                        f"The student's rating of how difficult they found "
                        f"'{course_name}' on a scale of 1 to 5, where 1 is very "
                        f"easy and 5 is very difficult"
                    ),
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="would_recommend_course",
                    description=(
                        f"Whether the student would recommend '{course_name}' to "
                        f"other students"
                    ),
                    field_type="multiple_choice",
                    choices=["yes", "no", "maybe"],
                    required=True,
                ),
            ],
        )
    elif outcome == "do_not_contact":
        logging.info("Student %s requested no further contact.", student_name)
        call.hangup(
            final_instructions=(
                "Acknowledge their request politely. Let them know they have been "
                "removed from our outreach list and will not be contacted again, and politely say goodbye."
            )
        )
    elif outcome == "wrong_number":
        logging.info("Wrong number reached for %s.", student_name)
        call.hangup(final_instructions="Apologize for the mistake and wish them well, and politely say goodbye.")
    else:
        logging.info("Could not reach %s (outcome: %s).", student_name, outcome)
        call.hangup()


@agent.on_task_complete("survey")
def on_survey_done(call: guava.Call) -> None:
    student_name = call.get_variable("name")
    course_overall = call.get_field("course_overall_rating")
    instructor = call.get_field("instructor_rating")

    if (course_overall is not None and course_overall <= 2) or (
        instructor is not None and instructor <= 2
    ):
        call.set_task(
            "low_score_followup",
            objective=(
                f"{student_name} gave a low rating. Ask what specifically could "
                f"have been better about the course or instruction. Listen carefully "
                f"and be empathetic. Assure them their feedback will be shared with "
                f"the department to help improve future offerings."
            ),
            checklist=[
                guava.Field(
                    key="most_valuable_aspect",
                    description="What the student found most valuable or memorable about the course, if anything",
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="suggested_improvements",
                    description="What specifically the student thinks could be improved about the course or instruction",
                    field_type="text",
                    required=True,
                ),
            ],
        )
    else:
        call.set_task(
            "positive_followup",
            objective=(
                f"Collect brief open-ended feedback from {student_name} on what "
                f"they found most valuable and any suggestions for improvement."
            ),
            checklist=[
                guava.Field(
                    key="most_valuable_aspect",
                    description="The aspect of the course the student found most valuable or memorable",
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="suggested_improvements",
                    description="Any improvements or changes the student would suggest for the course",
                    field_type="text",
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("low_score_followup")
def on_low_score_done(call: guava.Call) -> None:
    student_name = call.get_variable("name")
    call.hangup(
        final_instructions=(
            f"Thank {student_name} sincerely for sharing their candid feedback. "
            f"Let them know it genuinely helps Westfield University improve the "
            f"student experience. Assure them the feedback will be reviewed by the "
            f"department, and wish them the best for the upcoming term, and politely say goodbye."
        )
    )


@agent.on_task_complete("positive_followup")
def on_positive_done(call: guava.Call) -> None:
    student_name = call.get_variable("name")
    call.hangup(
        final_instructions=(
            f"Thank {student_name} sincerely for taking the time to share their "
            f"feedback. Let them know their input helps Westfield University "
            f"continue to improve. Wish them the best for the upcoming term and "
            f"wish them well, and politely say goodbye."
        )
    )


@agent.on_action_request
def on_action_request(call: guava.Call, intent_summary: str):
    return _mid_call_intent.classify(intent_summary)


@agent.on_action("do_not_contact")
def handle_dnc(call: guava.Call) -> None:
    logging.info("Student %s requested DNC mid-call.", call.get_variable("name"))
    call.hangup(
        final_instructions=(
            "Acknowledge their request. Let them know they've been removed from the "
            "contact list and won't be called again. Thank them and wish them well, and politely say goodbye."
        )
    )


@agent.on_action("speak_to_someone")
def handle_speak_to_someone(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            "Let them know that someone from Westfield University Academic Affairs "
            "will call them back within one business day. Ask if there's a preferred "
            "time and thank them for their patience, and politely say goodbye."
        )
    )


@agent.on_outbound_failed
def on_outbound_failed(event: guava.OutboundCallFailed) -> None:
    logging.error("Outbound call failed: %s (code %d)", event.error_reason, event.error_code)


@agent.on_session_end
def on_session_end(call: guava.Call, event: guava.BotSessionEnded) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "student_name": call.get_variable("name"),
        "course_name": call.get_variable("course_name"),
        "instructor_name": call.get_variable("instructor_name"),
        "term": call.get_variable("term"),
        "course_overall_rating": call.get_field("course_overall_rating"),
        "instructor_rating": call.get_field("instructor_rating"),
        "course_difficulty_rating": call.get_field("course_difficulty_rating"),
        "would_recommend_course": call.get_field("would_recommend_course"),
        "most_valuable_aspect": call.get_field("most_valuable_aspect"),
        "suggested_improvements": call.get_field("suggested_improvements"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


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
    parser.add_argument(
        "--from-number",
        default=os.environ.get("GUAVA_AGENT_NUMBER", ""),
        help="Caller ID / from number (defaults to GUAVA_AGENT_NUMBER env var).",
    )
    args = parser.parse_args()

    agent.call_phone(
        from_number=args.from_number,
        to_number=args.phone,
        variables={
            "name": args.name,
            "course_name": args.course_name,
            "instructor_name": args.instructor_name,
            "term": args.term,
        },
    )

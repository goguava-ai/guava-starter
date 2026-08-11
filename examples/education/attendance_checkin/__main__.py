# SDK conformance: guava-sdk 0.38.0 (2026-08-11)
import argparse
import json
import logging
import os
from datetime import datetime, timezone

import guava
from guava import logging_utils
from guava.helpers.llm import IntentRecognizer
from guava.events import BotSessionEnded, OutboundCallFailed

agent = guava.Agent(
    name="Casey",
    organization="Westfield Elementary School — Attendance Office",
    purpose=(
        "contact parents and guardians when a student has an unexcused absence "
        "to collect a reason and ensure the family is aware"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
    "speak_to_someone": "The caller wants to speak to a real person at the school, a teacher, or the principal",
})


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(
        contact_full_name=call.get_variable("parent_name"),
        voicemail_message=(
            f"Hi, this is Casey from Westfield Elementary School's Attendance "
            f"Office calling for {call.get_variable('parent_name')}. We're "
            f"reaching out regarding a student absence. Please call us back at "
            f"your convenience. Thank you."
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    parent_name = call.get_variable("parent_name")
    student_name = call.get_variable("student_name")
    absence_date = call.get_variable("absence_date")
    periods_missed = call.get_variable("periods_missed")

    if outcome == "available":
        call.set_task(
            "intake",
            objective=(
                f"You are calling {parent_name}, the parent or guardian of "
                f"{student_name}, because {student_name} has an unexcused absence "
                f"on {absence_date} for {periods_missed}. Collect the reason for "
                f"the absence and confirm the parent is aware."
            ),
            checklist=[
                guava.Say(
                    f"I'm reaching out because {student_name} was marked absent "
                    f"on {absence_date} for {periods_missed}, and we don't "
                    f"currently have an excuse on file. I just wanted to check "
                    f"in and make sure everything is okay."
                ),
                guava.Field(
                    key="absence_reason",
                    description=f"The reason for {student_name}'s absence",
                    field_type="multiple_choice",
                    choices=["illness", "family_emergency", "appointment", "other", "unknown"],
                    required=True,
                ),
                guava.Field(
                    key="parent_aware_of_absence",
                    description=(
                        f"Confirmation that {parent_name} is aware of and can "
                        f"account for {student_name}'s absence"
                    ),
                    field_type="multiple_choice",
                    choices=["yes", "no"],
                    required=True,
                ),
            ],
        )
    elif outcome == "do_not_contact":
        logging.info("Parent %s requested no further contact.", parent_name)
        call.hangup(
            final_instructions=(
                "Acknowledge their request politely. Let them know they have been "
                "removed from our automated call list. Note that the school may "
                "still need to reach them through other channels for required "
                "attendance notifications, and politely say goodbye."
            )
        )
    elif outcome == "wrong_number":
        logging.info("Wrong number reached for %s.", parent_name)
        call.hangup(final_instructions="Apologize for the mistake and wish them well, and politely say goodbye.")
    else:
        logging.info("Could not reach %s (outcome: %s).", parent_name, outcome)
        call.hangup()


@agent.on_task_complete("intake")
def on_intake_done(call: guava.Call) -> None:
    parent_name = call.get_variable("parent_name")
    student_name = call.get_variable("student_name")
    absence_reason = call.get_field("absence_reason")
    parent_aware = call.get_field("parent_aware_of_absence")

    if parent_aware == "no":
        logging.warning(
            "PRIORITY: Parent %s was NOT aware of %s's absence.",
            parent_name, student_name,
        )
        call.add_info("priority_flag", {
            "alert": "Parent was not aware of absence — school attendance office will follow up immediately.",
        })

    if absence_reason == "illness":
        call.set_task(
            "wellness_check",
            objective=(
                f"{student_name} is absent due to illness. Ask {parent_name} a few "
                f"follow-up questions to check on the student's well-being and "
                f"determine whether a doctor's note will be provided. Be caring "
                f"and supportive."
            ),
            checklist=[
                guava.Field(
                    key="expected_return_date",
                    description=f"The date {student_name} is expected to return to school",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="doctor_note_available",
                    description="Whether a doctor's note or official documentation will be provided",
                    field_type="multiple_choice",
                    choices=["yes", "no", "not sure"],
                    required=True,
                ),
                guava.Field(
                    key="additional_message_for_teacher",
                    description="Any message the parent would like passed along to the teacher or school",
                    field_type="text",
                    required=False,
                ),
            ],
        )
    elif absence_reason in ("other", "unknown"):
        call.set_task(
            "unexcused_followup",
            objective=(
                f"The absence reason for {student_name} is unexcused or unclear. "
                f"Let {parent_name} know this will be flagged for follow-up by the "
                f"attendance office. Be respectful but clear about the school's "
                f"attendance policy."
            ),
            checklist=[
                guava.Say(
                    f"Let {parent_name} know that without a documented excuse, the "
                    f"absence will be marked as unexcused in {student_name}'s "
                    f"attendance record. The attendance office may follow up if "
                    f"a pattern develops."
                ),
                guava.Field(
                    key="expected_return_date",
                    description=f"The date {student_name} is expected to return to school",
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="additional_message_for_teacher",
                    description="Any message the parent would like passed along to the teacher or school",
                    field_type="text",
                    required=False,
                ),
            ],
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {parent_name} for taking the time to speak with the school. "
                f"Let them know the absence has been noted as excused and will be "
                f"updated in the system. Wish {student_name} well and close warmly, and politely say goodbye."
            )
        )


@agent.on_task_complete("wellness_check")
def on_wellness_check_done(call: guava.Call) -> None:
    parent_name = call.get_variable("parent_name")
    student_name = call.get_variable("student_name")
    call.hangup(
        final_instructions=(
            f"Thank {parent_name} for the update. Wish {student_name} a speedy "
            f"recovery and let them know the school will look forward to having "
            f"them back. Close warmly, and politely say goodbye."
        )
    )


@agent.on_task_complete("unexcused_followup")
def on_unexcused_done(call: guava.Call) -> None:
    parent_name = call.get_variable("parent_name")
    call.hangup(
        final_instructions=(
            f"Thank {parent_name} for their time. Remind them that if they have "
            f"documentation for the absence, they can submit it to the attendance "
            f"office to have the record updated, and wish them a good day, and politely say goodbye."
        )
    )


@agent.on_action_request
def on_action_request(call: guava.Call, intent_summary: str):
    return _mid_call_intent.classify(intent_summary)


@agent.on_action("do_not_contact")
def handle_dnc(call: guava.Call) -> None:
    logging.info("Parent %s requested DNC mid-call.", call.get_variable("parent_name"))
    call.hangup(
        final_instructions=(
            "Acknowledge their request. Let them know they've been removed from the "
            "automated contact list. Note that the school may still need to reach "
            "them through other channels for required notifications, and wish them well, and politely say goodbye."
        )
    )


@agent.on_action("speak_to_someone")
def handle_speak_to_someone(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            "Let them know that someone from the Westfield Elementary attendance "
            "office will call them back within one business day. Ask if there's a "
            "preferred time and thank them for their patience, and politely say goodbye."
        )
    )


@agent.on_outbound_failed
def on_outbound_failed(event: OutboundCallFailed) -> None:
    logging.error("Outbound call failed: %s (code %d)", event.error_reason, event.error_code)


@agent.on_session_end
def on_session_end(call: guava.Call, event: BotSessionEnded) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "parent_name": call.get_variable("parent_name"),
        "student_name": call.get_variable("student_name"),
        "absence_date": call.get_variable("absence_date"),
        "periods_missed": call.get_variable("periods_missed"),
        "absence_reason": call.get_field("absence_reason"),
        "parent_aware_of_absence": call.get_field("parent_aware_of_absence"),
        "expected_return_date": call.get_field("expected_return_date"),
        "doctor_note_available": call.get_field("doctor_note_available"),
        "additional_message_for_teacher": call.get_field("additional_message_for_teacher"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


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
            "parent_name": args.parent_name,
            "student_name": args.student_name,
            "absence_date": args.absence_date,
            "periods_missed": args.periods_missed,
        },
    )

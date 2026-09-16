# SDK conformance: guava-sdk 0.43.0 (2026-09-15)
import argparse
import json
import logging
import os
from datetime import datetime, timezone

import guava
from guava import logging_utils
from guava.helpers.llm import IntentRecognizer
from guava.events import BotSessionEnded, OutboundCallFailed


# ---------------------------------------------------------------------------
# Mock API — simulates an enrollment system for demo purposes
# ---------------------------------------------------------------------------

ADMISSIONS_LINE = "+15551000400"

MOCK_ENROLLMENTS = {
    "STU-100201": {
        "student_name": "Marcus Chen",
        "dob": "2001-06-18",
        "term": "Fall 2026",
        "status": "enrolled",
        "status_detail": (
            "Enrollment is complete. All required documents have been received "
            "and the student is registered for 15 credit hours."
        ),
        "program": "Computer Science — B.S.",
        "credit_hours": 15,
    },
    "STU-100202": {
        "student_name": "Priya Sharma",
        "dob": "2002-09-04",
        "term": "Fall 2026",
        "status": "started_not_finished",
        "status_detail": (
            "The student began the enrollment process but has not completed it. "
            "Missing items: official high school transcript, immunization records."
        ),
        "program": "Biology — B.S.",
        "missing_items": "official high school transcript, immunization records",
    },
    "STU-100203": {
        "student_name": "Jalen Brooks",
        "dob": "2003-01-30",
        "term": "Fall 2026",
        "status": "not_started",
        "status_detail": (
            "The student was admitted but has not begun the enrollment process. "
            "No enrollment forms or documents have been submitted."
        ),
        "program": "Business Administration — B.A.",
    },
}


def lookup_enrollment(student_id, dob):
    record = MOCK_ENROLLMENTS.get(student_id)
    if record and record["dob"] == dob:
        return record
    return None


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

agent = guava.Agent(
    name="Drew",
    organization="Westfield University — Enrollment Services",
    purpose=(
        "follow up with students to check enrollment status, identify barriers "
        "to completing enrollment, and connect them with the right resources"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
    "speak_to_admissions": "The caller wants to speak to an admissions counselor or live person",
})


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(
        contact_full_name=call.get_variable("name"),
        voicemail_message=(
            f"Hi, this is Drew from Westfield University Enrollment Services "
            f"calling for {call.get_variable('name')}. We're reaching out about "
            f"your enrollment status. Please call us back at your convenience. "
            f"Thank you."
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    student_name = call.get_variable("name")

    if outcome == "available":
        call.set_task(
            "verify_identity",
            objective=(
                f"Verify the identity of {student_name} before sharing any "
                f"enrollment details. Ask for their date of birth. Do not share "
                f"any enrollment status or personal information until identity "
                f"is confirmed."
            ),
            checklist=[
                guava.Say(
                    f"I'm calling to check in on your enrollment. Before I "
                    f"share any details, I need to verify your identity with "
                    f"a quick question."
                ),
                guava.Field(
                    key="dob",
                    description="The student's date of birth for identity verification",
                    field_type="text",
                    required=True,
                ),
            ],
        )
    elif outcome == "do_not_contact":
        logging.info("Student %s requested no further contact.", student_name)
        call.hangup(
            final_instructions=(
                "Acknowledge their request. Let them know they will not be "
                "contacted again by phone and that future enrollment updates "
                "will be sent by email, and politely say goodbye."
            )
        )
    elif outcome == "wrong_number":
        logging.info("Wrong number for %s.", student_name)
        call.hangup(final_instructions="Apologize for the mistake and wish them well, and politely say goodbye.")
    else:
        logging.info("Could not reach %s (outcome: %s).", student_name, outcome)
        call.hangup()


@agent.on_task_complete("verify_identity")
def on_identity_verified(call: guava.Call) -> None:
    student_id = call.get_variable("student_id")
    dob = call.get_field("dob")
    record = lookup_enrollment(student_id, dob)

    if record is None:
        logging.warning("Identity verification failed for student %s.", student_id)
        call.hangup(
            final_instructions=(
                "Let them know the date of birth provided does not match our "
                "records. For security, you cannot share enrollment details. "
                "Suggest they contact Enrollment Services directly at "
                "1-800-555-0180 with their student ID handy, and politely say goodbye."
            )
        )
        return

    call.set_variable("enrollment_status", record["status"])
    call.set_variable("program", record.get("program", ""))

    call.add_info("enrollment_details", {
        "student_id": student_id,
        "status": record["status"],
        "status_detail": record["status_detail"],
        "program": record.get("program", ""),
        "missing_items": record.get("missing_items", ""),
        "credit_hours": record.get("credit_hours", ""),
    })

    if record["status"] == "enrolled":
        call.set_task(
            "confirm_enrollment",
            objective=(
                f"{call.get_variable('name')} is fully enrolled in "
                f"{record.get('program', 'their program')} for "
                f"{record.get('term', 'the upcoming term')}. Confirm their "
                f"enrollment is complete and ask if they have any questions "
                f"about next steps, orientation, or course registration."
            ),
            checklist=[
                guava.Field(
                    key="enrollment_confirmed",
                    description="Whether the student acknowledges their enrollment is complete",
                    field_type="multiple_choice",
                    choices=["yes", "has questions"],
                    required=True,
                ),
                guava.Field(
                    key="student_questions",
                    description="Any questions the student has about next steps, orientation, or registration",
                    field_type="text",
                    required=False,
                ),
            ],
        )
    elif record["status"] == "started_not_finished":
        call.set_task(
            "identify_barriers",
            objective=(
                f"{call.get_variable('name')} started the enrollment process but "
                f"has not completed it. The following items are still missing: "
                f"{record.get('missing_items', 'unknown items')}. "
                f"Identify what is preventing them from completing enrollment "
                f"and help them make a plan to finish."
            ),
            checklist=[
                guava.Say(
                    f"Let {call.get_variable('name')} know that their enrollment "
                    f"is incomplete. The following items are still needed: "
                    f"{record.get('missing_items', 'some required documents')}."
                ),
                guava.Field(
                    key="barrier_type",
                    description="The primary barrier preventing the student from completing enrollment",
                    field_type="multiple_choice",
                    choices=["financial", "technical", "personal", "missing_documents", "other"],
                    required=True,
                ),
                guava.Field(
                    key="barrier_detail",
                    description="Specific details about the barrier the student is facing",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="completion_plan",
                    description="The student's plan for submitting the missing items or resolving the barrier",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="submission_date_commitment",
                    description="The date by which the student commits to completing the missing items",
                    field_type="text",
                    required=True,
                ),
            ],
        )
    else:
        call.set_task(
            "re_engage",
            objective=(
                f"{call.get_variable('name')} was admitted but has not started the "
                f"enrollment process at all. Re-engage them — find out whether they "
                f"still intend to attend, what has been holding them back, and offer "
                f"to help them get started."
            ),
            checklist=[
                guava.Field(
                    key="still_planning_to_attend",
                    description="Whether the student still plans to attend Westfield University",
                    field_type="multiple_choice",
                    choices=["yes", "no", "undecided"],
                    required=True,
                ),
                guava.Field(
                    key="barrier_type",
                    description="The primary reason the student has not started enrollment",
                    field_type="multiple_choice",
                    choices=["financial", "technical", "personal", "chose_another_school", "other"],
                    required=True,
                ),
                guava.Field(
                    key="barrier_detail",
                    description="Specific details about what is holding the student back",
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="needs_help_getting_started",
                    description="Whether the student would like step-by-step help starting the enrollment process",
                    field_type="multiple_choice",
                    choices=["yes", "no"],
                    required=True,
                ),
            ],
        )


@agent.on_task_complete("confirm_enrollment")
def on_enrollment_confirmed(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            f"Thank {call.get_variable('name')} for their time. If they had "
            f"questions, let them know Enrollment Services will follow up by "
            f"email, and wish them an excellent start to the term, and politely say goodbye."
        )
    )


@agent.on_task_complete("identify_barriers")
def on_barriers_identified(call: guava.Call) -> None:
    barrier_type = call.get_field("barrier_type")

    if barrier_type == "financial":
        call.transfer(
            destination=ADMISSIONS_LINE,
            instructions=(
                f"The student ({call.get_variable('name')}) has financial barriers "
                f"preventing enrollment completion. Let them know you're connecting "
                f"them with an admissions counselor who can discuss financial aid "
                f"options. Reassure them that their information has been saved."
            ),
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {call.get_variable('name')} for sharing what's been holding "
                f"them up. Confirm their plan and submission date have been noted. "
                f"Let them know Enrollment Services is here to help if they run into "
                f"any issues, and wish them well, and politely say goodbye."
            )
        )


@agent.on_task_complete("re_engage")
def on_re_engagement_done(call: guava.Call) -> None:
    still_planning = call.get_field("still_planning_to_attend")
    barrier_type = call.get_field("barrier_type")

    if still_planning == "yes" and barrier_type == "financial":
        call.transfer(
            destination=ADMISSIONS_LINE,
            instructions=(
                f"The student ({call.get_variable('name')}) plans to attend but "
                f"has financial concerns. Connect them with an admissions counselor "
                f"who can help with financial aid. Reassure them."
            ),
        )
    elif still_planning in ("yes", "undecided"):
        call.hangup(
            final_instructions=(
                f"Thank {call.get_variable('name')} for their time. Let them know "
                f"Enrollment Services will send them a step-by-step guide by email "
                f"to help them get started, and wish them well, and politely say goodbye."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {call.get_variable('name')} for letting us know. Wish them "
                f"the best in their plans and let them know Westfield University's "
                f"admission remains open if they change their mind, and politely say goodbye."
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
            "Acknowledge their request. Let them know they will not be contacted "
            "again by phone and that future updates will be sent by email, and politely say goodbye."
        )
    )


@agent.on_action("speak_to_admissions")
def handle_transfer_request(call: guava.Call) -> None:
    call.transfer(
        destination=ADMISSIONS_LINE,
        instructions="Let them know you're connecting them with an admissions counselor now.",
    )


@agent.on_outbound_failed
def on_outbound_failed(event: OutboundCallFailed) -> None:
    logging.error("Outbound call failed: %s (code %d)", event.error_reason, event.error_code)


@agent.on_session_end
def on_session_end(call: guava.Call, event: BotSessionEnded) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "use_case": "enrollment_followup",
        "student_name": call.get_variable("name"),
        "student_id": call.get_variable("student_id"),
        "enrollment_status": call.get_variable("enrollment_status"),
        "program": call.get_variable("program"),
        "dob_verified": call.get_field("dob") is not None,
        "enrollment_confirmed": call.get_field("enrollment_confirmed"),
        "barrier_type": call.get_field("barrier_type"),
        "barrier_detail": call.get_field("barrier_detail"),
        "completion_plan": call.get_field("completion_plan"),
        "submission_date_commitment": call.get_field("submission_date_commitment"),
        "still_planning_to_attend": call.get_field("still_planning_to_attend"),
        "needs_help_getting_started": call.get_field("needs_help_getting_started"),
        "student_questions": call.get_field("student_questions"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound enrollment follow-up call for Westfield University"
    )
    parser.add_argument("phone", help="Phone number to dial")
    parser.add_argument("--name", required=True, help="Full name of the student")
    parser.add_argument("--student-id", required=True, help="Student ID (try STU-100201, STU-100202, or STU-100203)")
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
            "student_id": args.student_id,
        },
    )

# SDK conformance: guava-sdk 0.44.0 (2026-09-15)
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
# Mock API — simulates a resident eligibility backend for demo purposes
# ---------------------------------------------------------------------------

CASEWORKER_LINE = "+15551000400"

MOCK_RESIDENTS = {
    "RES-100201": {
        "name": "Maria Gonzalez",
        "dob": "1982-06-15",
        "status": "eligible",
        "program": "Utility Assistance Program",
        "status_detail": (
            "The resident qualifies based on household income below 200% of the "
            "federal poverty level. Enrollment can be completed by phone, online, "
            "or in person at the Community Services office."
        ),
    },
    "RES-100302": {
        "name": "James Wilson",
        "dob": "1975-03-22",
        "status": "ineligible",
        "program": "Utility Assistance Program",
        "status_detail": (
            "Household income exceeds the program threshold. The resident may "
            "qualify for the Low-Income Home Energy Assistance Program (LIHEAP) "
            "or assistance through local community action agencies."
        ),
    },
    "RES-100403": {
        "name": "Linda Chen",
        "dob": "1990-11-08",
        "status": "needs_documents",
        "program": "Utility Assistance Program",
        "status_detail": (
            "Eligibility cannot be confirmed until the following documents are "
            "submitted: proof of residency, most recent tax return, and a current "
            "utility bill."
        ),
        "documents_needed": "proof of residency, most recent tax return, and a current utility bill",
    },
}


def verify_resident(resident_id, dob):
    resident = MOCK_RESIDENTS.get(resident_id)
    if resident and resident["dob"] == dob:
        return resident
    return None


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

agent = guava.Agent(
    name="Dana",
    organization="City of Springfield — Community Services",
    purpose=(
        "verify resident identity, check eligibility for benefits programs, "
        "and guide eligible residents through initial enrollment steps"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
    "speak_to_caseworker": "The caller wants to speak to a caseworker, social worker, or real person",
})


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(
        contact_full_name=call.get_variable("resident_name"),
        voicemail_message=(
            f"Hi, this is Dana from the City of Springfield Community Services "
            f"calling for {call.get_variable('resident_name')}. We're reaching out "
            f"regarding a benefits program you may be eligible for. Please call us "
            f"back at 1-800-555-0200 at your convenience. Thank you."
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    resident_name = call.get_variable("resident_name")

    if outcome == "available":
        call.set_task(
            "verify_identity",
            objective=(
                f"Verify the identity of {resident_name} before sharing any "
                f"eligibility or program details. Ask for their date of birth. "
                f"Do not discuss benefits, eligibility, or program information "
                f"until identity is confirmed."
            ),
            checklist=[
                guava.Say(
                    "I'm calling because you may be eligible for a benefits program. "
                    "Before I share any details, I need to verify your identity with "
                    "a quick question."
                ),
                guava.Field(
                    key="dob",
                    description="The resident's date of birth for identity verification",
                    field_type="text",
                    required=True,
                ),
            ],
        )
    elif outcome == "do_not_contact":
        logging.info("Resident %s requested no further contact.", resident_name)
        call.hangup(
            final_instructions=(
                "Acknowledge their request. Let them know they will not be contacted "
                "again by phone regarding benefits programs, and politely say goodbye."
            )
        )
    elif outcome == "wrong_number":
        logging.info("Wrong number for %s.", resident_name)
        call.hangup(final_instructions="Apologize for the mistake and wish them well, and politely say goodbye.")
    else:
        logging.info("Could not reach %s (outcome: %s).", resident_name, outcome)
        call.hangup()


@agent.on_task_complete("verify_identity")
def on_identity_verified(call: guava.Call) -> None:
    resident_id = call.get_variable("resident_id")
    dob = call.get_field("dob")
    resident = verify_resident(resident_id, dob)

    if resident is None:
        logging.warning("Identity verification failed for resident %s.", resident_id)
        call.hangup(
            final_instructions=(
                "Let them know the date of birth provided does not match our records. "
                "For security, you cannot share program details. Suggest they call the "
                "Community Services office at 1-800-555-0200 with their identification "
                "documents handy, and politely say goodbye."
            )
        )
        return

    call.set_variable("eligibility_status", resident["status"])
    call.set_variable("program_name", resident["program"])

    call.add_info("resident_details", {
        "resident_id": resident_id,
        "program": resident["program"],
        "status": resident["status"],
        "status_detail": resident["status_detail"],
    })

    resident_name = call.get_variable("resident_name")

    if resident["status"] == "eligible":
        call.set_task(
            "enrollment",
            objective=(
                f"{resident_name} is eligible for the {resident['program']}. "
                f"Let them know they qualify, collect their household size and "
                f"current benefits information, and ask how they would prefer to "
                f"complete enrollment — online, by phone, or in person. A "
                f"Community Services representative will follow up with full "
                f"program details and next steps. Do NOT promise specific benefit "
                f"amounts or timelines."
            ),
            checklist=[
                guava.Say(
                    f"Great news — your identity has been verified, and based on "
                    f"our records, you are eligible for the {resident['program']}."
                ),
                guava.Field(
                    key="household_size",
                    description="Total number of people currently living in the resident's household",
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="currently_receiving_benefits",
                    description=(
                        "Whether the resident is currently receiving any other "
                        "government assistance or benefits programs"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="preferred_enrollment_method",
                    description="How the resident would prefer to complete enrollment",
                    field_type="multiple_choice",
                    choices=["online", "by phone", "in person"],
                    required=True,
                ),
                guava.Field(
                    key="program_questions",
                    description="Any questions the resident has about the program",
                    field_type="text",
                    required=False,
                ),
            ],
        )
    elif resident["status"] == "needs_documents":
        call.set_task(
            "documents_needed",
            objective=(
                f"{resident_name} may be eligible for the {resident['program']}, "
                f"but additional documentation is needed before eligibility can be "
                f"confirmed. Explain clearly what documents are required: "
                f"{resident.get('documents_needed', 'supporting documents')}. "
                f"Ask how they plan to submit the documents and confirm a timeline."
            ),
            checklist=[
                guava.Say(
                    f"Your identity has been verified. You may be eligible for the "
                    f"{resident['program']}, but we need a few additional documents "
                    f"before we can confirm your eligibility."
                ),
                guava.Field(
                    key="documents_understood",
                    description="Whether the resident understands which documents are needed",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="submission_method",
                    description="How the resident plans to submit the required documents",
                    field_type="multiple_choice",
                    choices=["email", "mail", "in person", "online portal"],
                    required=True,
                ),
                guava.Field(
                    key="submission_timeline",
                    description="When the resident expects to submit the required documents",
                    field_type="text",
                    required=True,
                ),
            ],
        )
    else:
        call.set_task(
            "ineligible_followup",
            objective=(
                f"{resident_name} does not currently qualify for the "
                f"{resident['program']}. Share the reason from the status detail "
                f"clearly and empathetically. Ask if they would like information "
                f"about other programs — if so, a caseworker can review their "
                f"situation and identify options. Offer to transfer to a "
                f"caseworker for anyone who wants to discuss further. "
                f"Do NOT speculate about future eligibility, make promises, or "
                f"name specific alternative programs."
            ),
            checklist=[
                guava.Say(
                    f"Your identity has been verified. Unfortunately, based on our "
                    f"current records, you do not qualify for the {resident['program']} "
                    f"at this time."
                ),
                guava.Field(
                    key="reason_understood",
                    description="Whether the resident understood the reason for ineligibility",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="wants_alternatives_info",
                    description="Whether the resident would like information about alternative programs",
                    field_type="multiple_choice",
                    choices=["yes", "no"],
                    required=True,
                ),
                guava.Field(
                    key="wants_caseworker",
                    description="Whether the resident would like to speak with a caseworker",
                    field_type="multiple_choice",
                    choices=["yes", "no"],
                    required=True,
                ),
            ],
        )


@agent.on_task_complete("enrollment")
def on_enrollment_done(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            f"Thank {call.get_variable('resident_name')} for their time. Confirm "
            f"their preferred enrollment method and let them know a Community Services "
            f"representative will follow up with next steps. Remind them they can call "
            f"1-800-555-0200 with any questions, and politely say goodbye."
        )
    )


@agent.on_task_complete("documents_needed")
def on_documents_done(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            f"Thank {call.get_variable('resident_name')} for their time. Remind them "
            f"of the documents needed and their stated submission plan. Let them know "
            f"eligibility will be reviewed once all documents are received. Provide the "
            f"office number 1-800-555-0200 for any questions, and politely say goodbye."
        )
    )


@agent.on_task_complete("ineligible_followup")
def on_ineligible_done(call: guava.Call) -> None:
    if call.get_field("wants_caseworker") == "yes":
        call.transfer(
            destination=CASEWORKER_LINE,
            instructions=(
                "Let the resident know you're connecting them with a caseworker "
                "who can discuss their options and alternative programs."
            ),
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {call.get_variable('resident_name')} for their time. "
                f"Remind them they can contact Community Services at 1-800-555-0200 "
                f"if their circumstances change or they have questions about other "
                f"programs, and wish them well, and politely say goodbye."
            )
        )


@agent.on_action_request
def on_action_request(call: guava.Call, intent_summary: str):
    return _mid_call_intent.classify(intent_summary)


@agent.on_action("do_not_contact")
def handle_dnc(call: guava.Call) -> None:
    logging.info("Resident %s requested DNC mid-call.", call.get_variable("resident_name"))
    call.hangup(
        final_instructions=(
            "Acknowledge their request. Let them know they will not be contacted "
            "again by phone regarding benefits programs, and wish them well, and politely say goodbye."
        )
    )


@agent.on_action("speak_to_caseworker")
def handle_transfer_request(call: guava.Call) -> None:
    call.transfer(
        destination=CASEWORKER_LINE,
        instructions="Let them know you're connecting them with a caseworker now.",
    )


@agent.on_outbound_failed
def on_outbound_failed(event: OutboundCallFailed) -> None:
    logging.error("Outbound call failed: %s (code %d)", event.error_reason, event.error_code)


@agent.on_session_end
def on_session_end(call: guava.Call, event: BotSessionEnded) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "use_case": "benefits_enrollment",
        "resident_name": call.get_variable("resident_name"),
        "resident_id": call.get_variable("resident_id"),
        "program_name": call.get_variable("program_name"),
        "eligibility_status": call.get_variable("eligibility_status"),
        "dob_verified": call.get_field("dob") is not None,
        "household_size": call.get_field("household_size"),
        "currently_receiving_benefits": call.get_field("currently_receiving_benefits"),
        "preferred_enrollment_method": call.get_field("preferred_enrollment_method"),
        "documents_understood": call.get_field("documents_understood"),
        "submission_method": call.get_field("submission_method"),
        "reason_understood": call.get_field("reason_understood"),
        "wants_caseworker": call.get_field("wants_caseworker"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound benefits enrollment call for City of Springfield Community Services"
    )
    parser.add_argument("phone", help="Resident phone number to call (E.164 format).")
    parser.add_argument("--name", required=True, help="Full name of the resident.")
    parser.add_argument(
        "--resident-id",
        required=True,
        help="Resident ID (try RES-100201, RES-100302, or RES-100403)",
    )
    parser.add_argument(
        "--program-name",
        default="the Utility Assistance Program",
        help='Name of the benefits program (default: "the Utility Assistance Program").',
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
            "resident_name": args.name,
            "resident_id": args.resident_id,
            "program_name": args.program_name,
        },
    )

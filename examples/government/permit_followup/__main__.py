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

agent = guava.Agent(
    name="Pat",
    organization="City of Springfield — Permitting Office",
    purpose=(
        "contact permit applicants with a status update on their application "
        "and guide them through next steps based on the current status"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
    "speak_to_someone": "The caller wants to speak to a permit office representative or real person",
})


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(
        contact_full_name=call.get_variable("applicant_name"),
        voicemail_message=(
            f"Hi, this is Pat from the City of Springfield Permitting Office "
            f"calling for {call.get_variable('applicant_name')} regarding permit "
            f"application {call.get_variable('permit_number')}. Please call us "
            f"back at your convenience. Thank you."
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    applicant_name = call.get_variable("applicant_name")
    permit_number = call.get_variable("permit_number")
    permit_status = call.get_variable("permit_status")
    status_detail = call.get_variable("status_detail")

    if outcome == "available":
        call.set_task(
            "followup",
            objective=(
                f"Inform {applicant_name} about the current status of their permit "
                f"application {permit_number}. The status is: {permit_status}. "
                f"Details: {status_detail}. Deliver the update clearly and confirm "
                f"the applicant understands their status and any required actions."
            ),
            checklist=[
                guava.Say(
                    f"I'm calling regarding your permit application number "
                    f"{permit_number}. I have an update on the status of your "
                    f"application."
                ),
                guava.Field(
                    key="status_acknowledged",
                    description=(
                        "Confirm that the applicant has heard and understood the "
                        "current status of their permit application"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="additional_questions",
                    description=(
                        "Ask if the applicant has any questions about the status "
                        "or the application process"
                    ),
                    field_type="text",
                    required=False,
                ),
            ],
        )
    elif outcome == "do_not_contact":
        logging.info("Applicant %s requested no further contact.", applicant_name)
        call.hangup(
            final_instructions=(
                "Acknowledge their request. Let them know they will not be contacted "
                "again by phone, and that any permit updates will be available online "
                "or by contacting the Permitting Office directly, and politely say goodbye."
            )
        )
    elif outcome == "wrong_number":
        logging.info("Wrong number reached for %s.", applicant_name)
        call.hangup(final_instructions="Apologize for the mistake and wish them well, and politely say goodbye.")
    else:
        logging.info("Could not reach %s (outcome: %s).", applicant_name, outcome)
        call.hangup()


@agent.on_task_complete("followup")
def on_followup_done(call: guava.Call) -> None:
    permit_status = call.get_variable("permit_status")
    applicant_name = call.get_variable("applicant_name")

    if permit_status == "approved":
        call.set_task(
            "approved_next_steps",
            objective=(
                f"{applicant_name}'s permit has been approved. Congratulate them "
                f"and let them know the approved permit is ready. Ask when they "
                f"plan to pick it up and whether they have any questions about "
                f"inspections. The Permitting Office will send detailed pickup "
                f"instructions, location, and any inspection scheduling "
                f"requirements by email."
            ),
            checklist=[
                guava.Field(
                    key="pickup_preference",
                    description="When the applicant plans to pick up the approved permit",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="inspection_questions",
                    description="Whether the applicant has questions about required inspections",
                    field_type="text",
                    required=False,
                ),
            ],
        )
    elif permit_status == "needs_revision":
        call.set_task(
            "revision_guidance",
            objective=(
                f"{applicant_name}'s permit application requires revisions before "
                f"it can be approved. Explain clearly what needs to be corrected "
                f"or resubmitted. Collect their plan for addressing the revisions "
                f"and a target resubmission date."
            ),
            checklist=[
                guava.Field(
                    key="revisions_understood",
                    description="Whether the applicant understands what revisions are needed",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="resubmission_method",
                    description="How the applicant plans to submit the revised application",
                    field_type="multiple_choice",
                    choices=["email", "mail", "in person", "online portal"],
                    required=True,
                ),
                guava.Field(
                    key="resubmission_date",
                    description="When the applicant expects to resubmit the corrected application",
                    field_type="text",
                    required=True,
                ),
            ],
        )
    else:
        # pending
        call.hangup(
            final_instructions=(
                f"Let {applicant_name} know that their application is still being "
                f"reviewed and provide the expected timeline. Reassure them that "
                f"they will be notified as soon as a decision is made. Remind them "
                f"they can check status online or call the Permitting Office. "
                f"Wish them a good day, and politely say goodbye."
            )
        )


@agent.on_task_complete("approved_next_steps")
def on_approved_done(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            f"Congratulate {call.get_variable('applicant_name')} on the approval. "
            f"Confirm the pickup details. Remind them to bring a valid photo ID. "
            f"Let them know they can contact the Permitting Office if they have "
            f"any additional questions, and wish them well, and politely say goodbye."
        )
    )


@agent.on_task_complete("revision_guidance")
def on_revision_done(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            f"Thank {call.get_variable('applicant_name')} for their time. Remind "
            f"them of the resubmission method and date they committed to. Let them "
            f"know the Permitting Office will continue processing once the revisions "
            f"are received, and wish them well, and politely say goodbye."
        )
    )


@agent.on_action_request
def on_action_request(call: guava.Call, intent_summary: str):
    return _mid_call_intent.classify(intent_summary)


@agent.on_action("do_not_contact")
def handle_dnc(call: guava.Call) -> None:
    logging.info("Applicant %s requested DNC mid-call.", call.get_variable("applicant_name"))
    call.hangup(
        final_instructions=(
            "Acknowledge their request. Let them know they will not be contacted "
            "again by phone regarding this permit application, and wish them well, and politely say goodbye."
        )
    )


@agent.on_action("speak_to_someone")
def handle_speak_to_someone(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            "Let them know that a Permitting Office representative will call them "
            "back within one business day. Ask if there's a preferred time and "
            "thank them for their patience, and politely say goodbye."
        )
    )


@agent.on_outbound_failed
def on_outbound_failed(event: OutboundCallFailed) -> None:
    logging.error("Outbound call failed: %s (code %d)", event.error_reason, event.error_code)


@agent.on_session_end
def on_session_end(call: guava.Call, event: BotSessionEnded) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "use_case": "permit_followup",
        "applicant_name": call.get_variable("applicant_name"),
        "permit_number": call.get_variable("permit_number"),
        "permit_status": call.get_variable("permit_status"),
        "status_acknowledged": call.get_field("status_acknowledged"),
        "additional_questions": call.get_field("additional_questions"),
        "pickup_preference": call.get_field("pickup_preference"),
        "revisions_understood": call.get_field("revisions_understood"),
        "resubmission_method": call.get_field("resubmission_method"),
        "resubmission_date": call.get_field("resubmission_date"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound permit follow-up call for City of Springfield Permitting Office."
    )
    parser.add_argument("phone", help="Applicant phone number to call (E.164 format).")
    parser.add_argument("--name", required=True, help="Full name of the permit applicant.")
    parser.add_argument("--permit-number", required=True, help="Permit or license application number.")
    parser.add_argument(
        "--permit-status",
        required=True,
        choices=["approved", "pending", "needs_revision"],
        help="Current status of the permit application.",
    )
    parser.add_argument(
        "--status-detail",
        required=True,
        help="Detailed explanation of the permit status and any required actions.",
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
            "applicant_name": args.name,
            "permit_number": args.permit_number,
            "permit_status": args.permit_status,
            "status_detail": args.status_detail,
        },
    )

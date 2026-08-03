# SDK conformance: guava-sdk 0.35.0 (2026-07-21)
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
    name="Reese",
    organization="Hargrove & Associates Law Firm",
    purpose=(
        "follow up on outstanding document requests related to a legal matter "
        "and log the client's response regarding document status and submission"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
    "speak_to_someone": "The caller wants to speak to their attorney or a staff member",
})


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    deadline = call.get_variable("deadline")
    call.reach_person(
        contact_full_name=call.get_variable("contact_name"),
        voicemail_message=(
            f"Hi, this is Reese from Hargrove & Associates calling for "
            f"{call.get_variable('contact_name')} regarding outstanding documents "
            f"for your legal matter. The deadline for submission is {deadline}. "
            f"Please call us back at your convenience. Thank you."
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    contact_name = call.get_variable("contact_name")
    matter_number = call.get_variable("matter_number")
    requested_documents = call.get_variable("requested_documents")
    deadline = call.get_variable("deadline")

    if outcome == "available":
        call.set_task(
            "document_followup",
            objective=(
                f"Follow up on outstanding documents for matter {matter_number}. "
                f"The documents requested are: {requested_documents}. The submission "
                f"deadline is {deadline}. Determine the status of the documents and "
                f"coordinate submission."
            ),
            checklist=[
                guava.Say(
                    f"I'm calling about matter {matter_number}. We had previously "
                    f"requested the following documents: {requested_documents}. The "
                    f"deadline for submission is {deadline}, and I'm following up to "
                    f"check on the status."
                ),
                guava.Field(
                    key="document_status",
                    description=(
                        "The current status of the requested documents"
                    ),
                    field_type="multiple_choice",
                    choices=["received_ready", "in_progress", "need_help"],
                    required=True,
                ),
            ],
        )
    elif outcome == "do_not_contact":
        logging.info("Client %s requested no further contact.", contact_name)
        call.hangup(
            final_instructions=(
                "Acknowledge their request. Let them know they will not be contacted "
                "again by phone and that document-related correspondence will continue "
                "by mail, and politely say goodbye."
            )
        )
    elif outcome == "wrong_number":
        logging.info("Wrong number for %s.", contact_name)
        call.hangup(final_instructions="Apologize for the mistake and wish them well, and politely say goodbye.")
    else:
        logging.info("Could not reach %s (outcome: %s).", contact_name, outcome)
        call.hangup()


@agent.on_task_complete("document_followup")
def on_followup_done(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    status = call.get_field("document_status")

    if status == "received_ready":
        call.set_task(
            "confirm_submission",
            objective=(
                f"{contact_name} has the documents ready. Confirm the submission "
                f"method and expected delivery date."
            ),
            checklist=[
                guava.Field(
                    key="submission_method",
                    description="How the client will submit the documents",
                    field_type="multiple_choice",
                    choices=["email", "mail", "drop_off", "fax"],
                    required=True,
                ),
                guava.Field(
                    key="submission_date",
                    description="The date by which the client will submit the documents",
                    field_type="text",
                    required=True,
                ),
            ],
        )
    elif status == "in_progress":
        call.set_task(
            "set_deadline_reminder",
            objective=(
                f"{contact_name} is still working on the documents. Set a deadline "
                f"reminder and confirm they understand the submission requirements."
            ),
            checklist=[
                guava.Field(
                    key="expected_completion",
                    description=(
                        "When the client expects to have the documents ready"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="reminder_preference",
                    description=(
                        "Whether the client would like a reminder call or email "
                        "before the deadline"
                    ),
                    field_type="multiple_choice",
                    choices=["call", "email", "no_reminder"],
                    required=True,
                ),
            ],
        )
    else:
        call.set_task(
            "offer_assistance",
            objective=(
                f"{contact_name} needs help with the documents. Find out what "
                f"specifically they are struggling with — for example, they may not "
                f"know where to obtain a document, may need records from a former "
                f"landlord or employer, or may have lost the original. Ask whether "
                f"any documents need to come from a third party. A staff member "
                f"will follow up to help — your job is to collect the details."
            ),
            checklist=[
                guava.Field(
                    key="help_needed",
                    description=(
                        "What specific help the client needs — for example, "
                        "understanding what qualifies, obtaining records from a "
                        "third party, or accessing documents they no longer have"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="third_party_release_needed",
                    description=(
                        "Whether any documents require a third-party release or "
                        "authorization to obtain"
                    ),
                    field_type="multiple_choice",
                    choices=["yes", "no", "not_sure"],
                    required=True,
                ),
            ],
        )


@agent.on_task_complete("confirm_submission")
def on_submission_confirmed(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    call.hangup(
        final_instructions=(
            f"Thank {contact_name} for having the documents ready, confirm the "
            f"submission method and date, let them know the firm will acknowledge "
            f"receipt, and wish them a good day, and politely say goodbye."
        )
    )


@agent.on_task_complete("set_deadline_reminder")
def on_reminder_set(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    deadline = call.get_variable("deadline")
    call.hangup(
        final_instructions=(
            f"Let {contact_name} know a reminder will be sent before the {deadline} "
            f"deadline, thank them for the update, and wish them a good day, and politely say goodbye."
        )
    )


@agent.on_task_complete("offer_assistance")
def on_assistance_offered(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    call.hangup(
        final_instructions=(
            f"Thank {contact_name} for explaining what they need, let them know "
            f"a staff member will follow up to help coordinate, and wish them a "
            f"good day, and politely say goodbye."
        )
    )


@agent.on_action_request
def on_action_request(call: guava.Call, intent_summary: str):
    return _mid_call_intent.classify(intent_summary)


@agent.on_action("do_not_contact")
def handle_dnc(call: guava.Call) -> None:
    logging.info("Client %s requested DNC mid-call.", call.get_variable("contact_name"))
    call.hangup(
        final_instructions=(
            "Acknowledge their request. Let them know they have been removed from "
            "the contact list and will not be called again, and wish them well, and politely say goodbye."
        )
    )


@agent.on_action("speak_to_someone")
def handle_speak_to_someone(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            "Let them know their attorney or a staff member will call them back "
            "within one business day. Ask if there's a preferred time and thank them, and politely say goodbye."
        )
    )


@agent.on_outbound_failed
def on_outbound_failed(event: OutboundCallFailed) -> None:
    logging.error("Outbound call failed: %s (code %d)", event.error_reason, event.error_code)


@agent.on_session_end
def on_session_end(call: guava.Call, event: BotSessionEnded) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "use_case": "document_followup",
        "contact_name": call.get_variable("contact_name"),
        "matter_number": call.get_variable("matter_number"),
        "requested_documents": call.get_variable("requested_documents"),
        "deadline": call.get_variable("deadline"),
        "document_status": call.get_field("document_status"),
        "submission_method": call.get_field("submission_method"),
        "submission_date": call.get_field("submission_date"),
        "expected_completion": call.get_field("expected_completion"),
        "reminder_preference": call.get_field("reminder_preference"),
        "help_needed": call.get_field("help_needed"),
        "third_party_release_needed": call.get_field("third_party_release_needed"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound document follow-up call for Hargrove & Associates"
    )
    parser.add_argument("phone", help="Phone number to dial")
    parser.add_argument("--name", required=True, help="Full name of the contact")
    parser.add_argument("--matter-number", required=True, help="Matter or case number")
    parser.add_argument(
        "--requested-documents",
        required=True,
        help="Description of the outstanding documents",
    )
    parser.add_argument(
        "--deadline",
        required=True,
        help="Submission deadline for the documents",
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
            "contact_name": args.name,
            "matter_number": args.matter_number,
            "requested_documents": args.requested_documents,
            "deadline": args.deadline,
        },
    )

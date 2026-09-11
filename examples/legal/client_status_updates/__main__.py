# SDK conformance: guava-sdk 0.42.0 (2026-09-08)
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
    name="Harper",
    organization="Hargrove & Associates Law Firm",
    purpose=(
        "proactively inform clients of the current status of their legal matter, "
        "confirm they understand the update and next steps, and capture any "
        "questions they would like relayed to their attorney"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
    "speak_to_someone": "The caller wants to speak to their attorney or a live person",
})


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(
        contact_full_name=call.get_variable("contact_name"),
        voicemail_message=(
            f"Hi, this is Harper from Hargrove & Associates calling for "
            f"{call.get_variable('contact_name')} with a status update on your "
            f"legal matter. Please call us back at your convenience. Thank you."
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    contact_name = call.get_variable("contact_name")
    matter_number = call.get_variable("matter_number")
    status_update = call.get_variable("status_update")
    next_step = call.get_variable("next_step")

    if outcome == "available":
        call.set_task(
            "status_update",
            objective=(
                f"Deliver a case status update to {contact_name} for matter "
                f"{matter_number}. The current status is: {status_update}. "
                f"The next step is: {next_step}. Confirm the client understands "
                f"and capture any questions for their attorney."
            ),
            checklist=[
                guava.Say(
                    f"I have an update on matter {matter_number}. Here is the "
                    f"current status: {status_update}. Regarding next steps: "
                    f"{next_step}."
                ),
                guava.Field(
                    key="update_understood",
                    description=(
                        "Confirmation that the client has heard and understood the "
                        "status update and next steps"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="questions_for_attorney",
                    description=(
                        "Any questions the client would like relayed to their attorney"
                    ),
                    field_type="text",
                    required=False,
                ),
            ],
        )
    elif outcome == "do_not_contact":
        logging.info("Client %s requested no further contact.", contact_name)
        call.hangup(
            final_instructions=(
                "Acknowledge their request. Let them know they will not be contacted "
                "again by phone and that case updates will be sent by mail or through "
                "the client portal, and politely say goodbye."
            )
        )
    elif outcome == "wrong_number":
        logging.info("Wrong number for %s.", contact_name)
        call.hangup(final_instructions="Apologize for the mistake and wish them well, and politely say goodbye.")
    else:
        logging.info("Could not reach %s (outcome: %s).", contact_name, outcome)
        call.hangup()


@agent.on_task_complete("status_update")
def on_update_done(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    questions = call.get_field("questions_for_attorney")

    if questions:
        call.set_task(
            "schedule_followup",
            objective=(
                f"{contact_name} has questions for their attorney. Determine if "
                f"they would like to schedule a follow-up call, request documents "
                f"be sent, or if they have no further needs at this time."
            ),
            checklist=[
                guava.Field(
                    key="followup_preference",
                    description=(
                        "What the client would like as a next step: schedule a "
                        "callback with their attorney, receive documents by email, "
                        "or no further action needed"
                    ),
                    field_type="multiple_choice",
                    choices=["schedule_callback", "request_documents", "no_action"],
                    required=True,
                ),
                guava.Field(
                    key="preferred_callback_time",
                    description=(
                        "If scheduling a callback, the client's preferred day and "
                        "time. Leave blank if not applicable."
                    ),
                    field_type="text",
                    required=False,
                ),
            ],
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {contact_name} for their time. Remind them that Hargrove "
                f"& Associates is committed to keeping them informed and that they "
                f"can reach the firm anytime with questions, and wish them a good day, and politely say goodbye."
            )
        )


@agent.on_task_complete("schedule_followup")
def on_followup_scheduled(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    preference = call.get_field("followup_preference")

    if preference == "schedule_callback":
        call.hangup(
            final_instructions=(
                f"Confirm that {contact_name}'s preferred callback time has been "
                f"noted and their attorney will reach out accordingly. Thank them "
                f"and wish them a good day, and politely say goodbye."
            )
        )
    elif preference == "request_documents":
        call.hangup(
            final_instructions=(
                f"Confirm that the requested documents will be sent to {contact_name} "
                f"by email, and wish them a good day, and politely say goodbye."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {contact_name} for their time. Remind them they can contact "
                f"the firm anytime, and wish them a good day, and politely say goodbye."
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
        "use_case": "client_status_update",
        "contact_name": call.get_variable("contact_name"),
        "matter_number": call.get_variable("matter_number"),
        "update_understood": call.get_field("update_understood"),
        "questions_for_attorney": call.get_field("questions_for_attorney"),
        "followup_preference": call.get_field("followup_preference"),
        "preferred_callback_time": call.get_field("preferred_callback_time"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound client status update call for Hargrove & Associates"
    )
    parser.add_argument("phone", help="Phone number to dial")
    parser.add_argument("--name", required=True, help="Full name of the client")
    parser.add_argument("--matter-number", required=True, help="Matter or case number")
    parser.add_argument(
        "--status-update",
        required=True,
        help="Text describing the current status of the matter",
    )
    parser.add_argument(
        "--next-step",
        required=True,
        help="Text describing the next step or action in the matter",
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
            "status_update": args.status_update,
            "next_step": args.next_step,
        },
    )

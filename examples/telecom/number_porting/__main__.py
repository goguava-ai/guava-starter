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
    name="Blair",
    organization="Nexus Mobile — Porting Team",
    purpose=(
        "provide customers with a proactive update on their number port status, "
        "confirm completion, explain timelines for in-progress ports, or collect "
        "additional information needed to resolve port issues"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
    "speak_to_someone": "The caller wants to speak to a real person or porting specialist",
})


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(
        contact_full_name=call.get_variable("customer_name"),
        voicemail_message=(
            f"Hi, this is Blair from the Nexus Mobile Porting Team calling for "
            f"{call.get_variable('customer_name')} with an update on your number "
            f"port. No action needed right now — please call us back at your "
            f"convenience. Thank you!"
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    customer_name = call.get_variable("customer_name")
    number_being_ported = call.get_variable("number_being_ported")
    port_status = call.get_variable("port_status")

    if outcome == "available":
        if port_status == "complete":
            call.set_task(
                "deliver_complete_update",
                objective=(
                    f"Notify {customer_name} that the port of {number_being_ported} "
                    f"to Nexus Mobile is complete. Confirm the number is active on "
                    f"their new account and welcome them."
                ),
                checklist=[
                    guava.Say(
                        f"Great news — the port of your number ending in "
                        f"{number_being_ported[-4:]} is complete! Your number is "
                        f"now active on your Nexus Mobile account. Welcome aboard!"
                    ),
                    guava.Field(
                        key="service_confirmed",
                        description="Whether the customer confirms their number is working on Nexus Mobile",
                        field_type="multiple_choice",
                        choices=["yes", "no", "not_checked_yet"],
                        required=True,
                    ),
                    guava.Field(
                        key="questions",
                        description="Any questions the customer has about their new service",
                        field_type="text",
                        required=False,
                    ),
                ],
            )
        elif port_status == "in_progress":
            expected_date = call.get_variable("expected_date")
            call.set_task(
                "deliver_progress_update",
                objective=(
                    f"Update {customer_name} that the port of {number_being_ported} "
                    f"is in progress. The expected completion date is {expected_date}. "
                    f"Explain what to expect during the transition."
                ),
                checklist=[
                    guava.Say(
                        f"I have an update on your number port. Your number "
                        f"ending in {number_being_ported[-4:]} is currently being "
                        f"transferred and is expected to complete by "
                        f"{expected_date}. During the brief switchover, you may "
                        f"experience a short service interruption — this is normal."
                    ),
                    guava.Field(
                        key="update_acknowledged",
                        description="Whether the customer understands the timeline and what to expect",
                        field_type="text",
                        required=True,
                    ),
                    guava.Field(
                        key="questions",
                        description="Any questions about the porting timeline or process",
                        field_type="text",
                        required=False,
                    ),
                ],
            )
        else:
            issue_detail = call.get_variable("issue_detail")
            call.set_task(
                "deliver_issue_update",
                objective=(
                    f"Notify {customer_name} that there is an issue with the port of "
                    f"{number_being_ported}: {issue_detail}. Explain the problem and "
                    f"collect any additional information needed to resolve it."
                ),
                checklist=[
                    guava.Say(
                        f"I'm calling about your number port for the number "
                        f"ending in {number_being_ported[-4:]}. Unfortunately, "
                        f"we've encountered an issue: {issue_detail}. I need to "
                        f"collect some additional information to get this resolved."
                    ),
                    guava.Field(
                        key="issue_acknowledged",
                        description="Whether the customer understands the issue",
                        field_type="text",
                        required=True,
                    ),
                    guava.Field(
                        key="additional_info",
                        description=(
                            "Additional information collected from the customer to resolve "
                            "the port issue (account PIN, authorized name, carrier details)"
                        ),
                        field_type="text",
                        required=True,
                    ),
                ],
            )
    elif outcome == "do_not_contact":
        logging.info("Customer %s requested no further contact.", customer_name)
        call.hangup(
            final_instructions=(
                "Acknowledge their request. Let them know they will not be contacted "
                "again by phone. Note that port status updates will be sent by email, and politely say goodbye."
            )
        )
    elif outcome == "wrong_number":
        logging.info("Wrong number reached for %s.", customer_name)
        call.hangup(final_instructions="Apologize for the mistake and wish them well, and politely say goodbye.")
    else:
        logging.info("Could not reach %s (outcome: %s).", customer_name, outcome)
        call.hangup()


@agent.on_task_complete("deliver_complete_update")
def on_complete_done(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            f"Welcome {call.get_variable('customer_name')} to Nexus Mobile. "
            f"Let them know they can reach customer support anytime, and wish them well, and politely say goodbye."
        )
    )


@agent.on_task_complete("deliver_progress_update")
def on_progress_done(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            f"Thank {call.get_variable('customer_name')} for their patience. Remind "
            f"them to keep their old phone powered on until the port completes. "
            f"Wish them a great day, and politely say goodbye."
        )
    )


@agent.on_task_complete("deliver_issue_update")
def on_issue_done(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            f"Thank {call.get_variable('customer_name')} for providing the additional "
            f"information. Let them know the porting team will retry the port within "
            f"one business day and send a status update, and wish them well, and politely say goodbye."
        )
    )


@agent.on_action_request
def on_action_request(call: guava.Call, intent_summary: str):
    return _mid_call_intent.classify(intent_summary)


@agent.on_action("do_not_contact")
def handle_dnc(call: guava.Call) -> None:
    logging.info("Customer %s requested DNC mid-call.", call.get_variable("customer_name"))
    call.hangup(
        final_instructions=(
            "Acknowledge their request. Let them know they've been removed from the "
            "contact list and won't be called again, and wish them well, and politely say goodbye."
        )
    )


@agent.on_action("speak_to_someone")
def handle_speak_to_someone(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            "Let them know that a Nexus Mobile porting specialist will call them back "
            "within one business day, thank them for their time, and politely say goodbye."
        )
    )


@agent.on_outbound_failed
def on_outbound_failed(event: OutboundCallFailed) -> None:
    logging.error("Outbound call failed: %s (code %d)", event.error_reason, event.error_code)


@agent.on_session_end
def on_session_end(call: guava.Call, event: BotSessionEnded) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "customer_name": call.get_variable("customer_name"),
        "number_being_ported": call.get_variable("number_being_ported"),
        "port_status": call.get_variable("port_status"),
        "service_confirmed": call.get_field("service_confirmed"),
        "update_acknowledged": call.get_field("update_acknowledged"),
        "issue_acknowledged": call.get_field("issue_acknowledged"),
        "additional_info": call.get_field("additional_info"),
        "questions": call.get_field("questions"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound number porting status call for Nexus Mobile"
    )
    parser.add_argument("phone", help="Customer phone number to call")
    parser.add_argument("--name", required=True, help="Customer full name")
    parser.add_argument(
        "--number-being-ported", required=True, help="The phone number being ported"
    )
    parser.add_argument(
        "--port-status",
        required=True,
        choices=["complete", "in_progress", "issue"],
        help="Current port status",
    )
    parser.add_argument("--expected-date", default="", help="Expected completion date (for in_progress)")
    parser.add_argument("--issue-detail", default="", help="Issue details (for issue status)")
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
            "customer_name": args.name,
            "number_being_ported": args.number_being_ported,
            "port_status": args.port_status,
            "expected_date": args.expected_date,
            "issue_detail": args.issue_detail,
        },
    )

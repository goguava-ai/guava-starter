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
    name="Parker",
    organization="SwiftShip Logistics - Dispatch",
    purpose=(
        "perform a status check-in with carriers on active loads, confirm ETAs, "
        "collect delay reasons, and escalate issues requiring dispatch intervention"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
    "speak_to_dispatch": "The caller wants to speak to a live dispatcher or supervisor",
})


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(
        contact_full_name=call.get_variable("driver_name"),
        voicemail_message=(
            f"Hi, this is Parker from SwiftShip Logistics Dispatch calling for "
            f"{call.get_variable('driver_name')} regarding load number "
            f"{call.get_variable('load_number')} headed to "
            f"{call.get_variable('destination')}. Please call dispatch back at "
            f"your earliest convenience for a status update. Thank you and drive safe!"
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    driver_name = call.get_variable("driver_name")
    load_number = call.get_variable("load_number")
    destination = call.get_variable("destination")
    scheduled_arrival = call.get_variable("scheduled_arrival")

    if outcome == "available":
        call.set_task(
            "status_checkin",
            objective=(
                f"Check in with {driver_name} regarding load number {load_number} "
                f"headed to {destination}. The scheduled arrival is {scheduled_arrival}. "
                f"Determine the current delivery status. Collect current location and "
                f"estimated arrival time."
            ),
            checklist=[
                guava.Say(
                    f"I'm calling for a quick status update on load number "
                    f"{load_number} heading to {destination}, scheduled to arrive "
                    f"{scheduled_arrival}."
                ),
                guava.Field(
                    key="current_location",
                    description="The driver's current location, such as a city, highway, or mile marker",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="estimated_arrival",
                    description="The driver's current estimated arrival time at the destination",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="delivery_status",
                    description="Current delivery status",
                    field_type="multiple_choice",
                    choices=["on_time", "delayed", "issue"],
                    required=True,
                ),
            ],
        )
    elif outcome == "do_not_contact":
        logging.info("Driver %s requested no further contact.", driver_name)
        call.hangup(
            final_instructions=(
                "Acknowledge their request. Let them know they have been removed from "
                "the check-in call list and will not be contacted again, and politely say goodbye."
            )
        )
    elif outcome == "wrong_number":
        logging.info("Wrong number reached for driver %s.", driver_name)
        call.hangup(final_instructions="Apologize for the mistake and wish them well, and politely say goodbye.")
    else:
        logging.info("Could not reach driver %s (outcome: %s).", driver_name, outcome)
        call.hangup()


@agent.on_task_complete("status_checkin")
def on_status_checkin_done(call: guava.Call) -> None:
    status = call.get_field("delivery_status")
    driver_name = call.get_variable("driver_name")

    if status == "on_time":
        call.hangup(
            final_instructions=(
                f"Confirm the ETA with {driver_name}. Thank them for the update and "
                f"let them know dispatch has noted the on-time status. Wish them a safe "
                f"drive and let them know to call in if anything changes, and politely say goodbye."
            )
        )
    elif status == "delayed":
        call.set_task(
            "collect_delay_details",
            objective=(
                f"{driver_name} reports load {call.get_variable('load_number')} is delayed. "
                f"Collect the new estimated arrival time, the reason for the delay, and "
                f"whether the driver needs any support from dispatch."
            ),
            checklist=[
                guava.Field(
                    key="new_eta",
                    description="The updated estimated arrival time given the delay",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="delay_reason",
                    description="The reason for the delay (weather, traffic, mechanical, rest stop, etc.)",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="needs_dispatch_support",
                    description="Whether the driver needs any support from dispatch to resolve the delay",
                    field_type="multiple_choice",
                    choices=["yes", "no"],
                    required=True,
                ),
            ],
        )
    else:
        call.set_task(
            "collect_issue_details",
            objective=(
                f"{driver_name} reports an issue with load {call.get_variable('load_number')}. "
                f"Collect details about the issue, whether the load is safe and secure, "
                f"and whether the driver needs immediate assistance."
            ),
            checklist=[
                guava.Field(
                    key="issue_description",
                    description="A description of the issue the driver is experiencing",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="load_secure",
                    description="Whether the load is currently safe and secure",
                    field_type="multiple_choice",
                    choices=["yes", "no", "not sure"],
                    required=True,
                ),
                guava.Field(
                    key="needs_immediate_assistance",
                    description="Whether the driver needs immediate assistance from dispatch",
                    field_type="multiple_choice",
                    choices=["yes", "no"],
                    required=True,
                ),
            ],
        )


@agent.on_task_complete("collect_delay_details")
def on_delay_details_done(call: guava.Call) -> None:
    driver_name = call.get_variable("driver_name")
    call.hangup(
        final_instructions=(
            f"Thank {driver_name} for the update. Let them know dispatch will relay "
            f"the revised ETA to the shipper and receiver. If they indicated they need "
            f"support, confirm that dispatch will follow up shortly, and wish them a safe drive, and politely say goodbye."
        )
    )


@agent.on_task_complete("collect_issue_details")
def on_issue_details_done(call: guava.Call) -> None:
    driver_name = call.get_variable("driver_name")
    call.hangup(
        final_instructions=(
            f"Thank {driver_name} for reporting the issue. Let them know dispatch has "
            f"logged the details and will coordinate next steps. If they need immediate "
            f"assistance, confirm that a dispatcher will call them back within 15 minutes. "
            f"Remind them to stay safe, and politely say goodbye."
        )
    )


@agent.on_action_request
def on_action_request(call: guava.Call, intent_summary: str):
    return _mid_call_intent.classify(intent_summary)


@agent.on_action("do_not_contact")
def handle_dnc(call: guava.Call) -> None:
    logging.info("Driver %s requested DNC mid-call.", call.get_variable("driver_name"))
    call.hangup(
        final_instructions=(
            "Acknowledge their request. Let them know they've been removed from the "
            "check-in call list and won't be contacted again, and wish them well, and politely say goodbye."
        )
    )


@agent.on_action("speak_to_dispatch")
def handle_speak_to_dispatch(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            "Let them know that a live dispatcher will call them back within "
            "15 minutes. Ask if there is anything urgent they need to relay in "
            "the meantime and thank them for their patience, and politely say goodbye."
        )
    )


@agent.on_outbound_failed
def on_outbound_failed(event: OutboundCallFailed) -> None:
    logging.error("Outbound call failed: %s (code %d)", event.error_reason, event.error_code)


@agent.on_session_end
def on_session_end(call: guava.Call, event: BotSessionEnded) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "load_number": call.get_variable("load_number"),
        "destination": call.get_variable("destination"),
        "scheduled_arrival": call.get_variable("scheduled_arrival"),
        "driver_name": call.get_variable("driver_name"),
        "current_location": call.get_field("current_location"),
        "estimated_arrival": call.get_field("estimated_arrival"),
        "delivery_status": call.get_field("delivery_status"),
        "new_eta": call.get_field("new_eta"),
        "delay_reason": call.get_field("delay_reason"),
        "needs_dispatch_support": call.get_field("needs_dispatch_support"),
        "issue_description": call.get_field("issue_description"),
        "load_secure": call.get_field("load_secure"),
        "needs_immediate_assistance": call.get_field("needs_immediate_assistance"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound carrier check-in call for SwiftShip Logistics"
    )
    parser.add_argument("phone", help="Driver or carrier phone number to call")
    parser.add_argument("--driver-name", required=True, help="Full name of the driver")
    parser.add_argument("--load-number", required=True, help="Load or shipment number")
    parser.add_argument("--destination", required=True, help="Delivery destination")
    parser.add_argument("--scheduled-arrival", required=True, help="Originally scheduled arrival time/date")
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
            "driver_name": args.driver_name,
            "load_number": args.load_number,
            "destination": args.destination,
            "scheduled_arrival": args.scheduled_arrival,
        },
    )

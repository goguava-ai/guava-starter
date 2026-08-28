# SDK conformance: guava-sdk 0.40.0 (2026-08-26)
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
    name="Taylor",
    organization="Lakeside Auto Group",
    purpose=(
        "call customers who are due for routine maintenance and help them "
        "confirm or reschedule their upcoming service appointment"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
    "speak_to_someone": "The caller wants to speak to a real person, a service advisor, or a manager",
})


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(
        contact_full_name=call.get_variable("customer_name"),
        voicemail_message=(
            f"Hi, this is Taylor from Lakeside Auto Group calling for "
            f"{call.get_variable('customer_name')}. We're reaching out about your "
            f"vehicle's upcoming service. Please call us back at your convenience. "
            f"Thank you!"
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    customer_name = call.get_variable("customer_name")
    vehicle = call.get_variable("vehicle")
    service_type = call.get_variable("service_type")
    mileage = call.get_variable("mileage")

    if outcome == "available":
        call.set_task(
            "service_reminder",
            objective=(
                f"Remind {customer_name} that their {vehicle} is due for "
                f"{service_type} at {mileage} miles. Ask whether they would like "
                f"to confirm an appointment, reschedule, or decline for now."
            ),
            checklist=[
                guava.Say(
                    f"Explain that their {vehicle} is due for {service_type} "
                    f"based on the current mileage of {mileage}."
                ),
                guava.Field(
                    key="service_response",
                    description="The customer's response to the service reminder",
                    field_type="multiple_choice",
                    choices=["confirm", "reschedule", "decline"],
                    required=True,
                ),
            ],
        )
    elif outcome == "do_not_contact":
        logging.info("Customer %s requested no further contact.", customer_name)
        call.hangup(
            final_instructions=(
                "Acknowledge their request politely. Let them know they have been "
                "removed from our reminder list and will not be contacted again, and politely say goodbye."
            )
        )
    elif outcome == "wrong_number":
        logging.info("Wrong number reached for %s.", customer_name)
        call.hangup(final_instructions="Apologize for the mistake and wish them well, and politely say goodbye.")
    else:
        logging.info("Could not reach %s (outcome: %s).", customer_name, outcome)
        call.hangup()


@agent.on_task_complete("service_reminder")
def on_service_reminder_done(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    response = call.get_field("service_response")

    if response == "confirm":
        call.set_task(
            "confirm_appointment",
            objective=(
                f"{customer_name} wants to confirm their service appointment. "
                f"Collect their preferred date and time, and whether they need a "
                f"loaner car. Let them know a confirmation text will be sent."
            ),
            checklist=[
                guava.Field(
                    key="appointment_date_preference",
                    description="The customer's preferred date for their service appointment",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="appointment_time_preference",
                    description="The customer's preferred time of day (morning, afternoon, or specific time)",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="loaner_car_needed",
                    description="Whether the customer will need a loaner car during the service",
                    field_type="multiple_choice",
                    choices=["yes", "no"],
                    required=True,
                ),
                guava.Field(
                    key="additional_service_requests",
                    description="Any additional services or concerns the customer would like addressed during the visit",
                    field_type="text",
                    required=False,
                ),
            ],
        )
    elif response == "reschedule":
        call.set_task(
            "reschedule_appointment",
            objective=(
                f"{customer_name} would like to reschedule. Collect their preferred "
                f"date and time for the service appointment."
            ),
            checklist=[
                guava.Field(
                    key="reschedule_date_preference",
                    description="The customer's preferred date for the rescheduled appointment",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="reschedule_time_preference",
                    description="The customer's preferred time of day (morning, afternoon, or specific time)",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="loaner_car_needed",
                    description="Whether the customer will need a loaner car during the service",
                    field_type="multiple_choice",
                    choices=["yes", "no"],
                    required=True,
                ),
            ],
        )
    else:
        call.set_task(
            "decline_followup",
            objective=(
                f"{customer_name} is declining the service appointment for now. "
                f"Ask briefly if there is a reason — such as cost, timing, or having "
                f"service done elsewhere — and offer to call back at a better time."
            ),
            checklist=[
                guava.Field(
                    key="decline_reason",
                    description="The reason the customer is declining the service appointment",
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="callback_requested",
                    description="Whether the customer would like a callback at a later date",
                    field_type="multiple_choice",
                    choices=["yes", "no"],
                    required=True,
                ),
                guava.Field(
                    key="callback_timeframe",
                    description="When the customer would like to be called back, if requested",
                    field_type="text",
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("confirm_appointment")
def on_confirmed(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    call.hangup(
        final_instructions=(
            f"Thank {customer_name} for scheduling their service. Confirm their "
            f"appointment details and let them know a confirmation text will be "
            f"sent, and wish them a great day, and politely say goodbye."
        )
    )


@agent.on_task_complete("reschedule_appointment")
def on_rescheduled(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    call.hangup(
        final_instructions=(
            f"Thank {customer_name} for rescheduling. Confirm their new preferred "
            f"date and time have been noted and the service team will confirm. "
            f"Wish them a great day, and politely say goodbye."
        )
    )


@agent.on_task_complete("decline_followup")
def on_declined(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    call.hangup(
        final_instructions=(
            f"Thank {customer_name} for their time. If they requested a callback, "
            f"confirm it has been noted. Remind them that Lakeside Auto Group is "
            f"here whenever they're ready, and wish them a great day, and politely say goodbye."
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
            "Let them know that someone from the Lakeside Auto Group service team "
            "will call them back within one business day. Ask if there's a preferred "
            "time and thank them for their patience, and politely say goodbye."
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
        "vehicle": call.get_variable("vehicle"),
        "service_type": call.get_variable("service_type"),
        "mileage": call.get_variable("mileage"),
        "service_response": call.get_field("service_response"),
        "appointment_date_preference": call.get_field("appointment_date_preference"),
        "appointment_time_preference": call.get_field("appointment_time_preference"),
        "reschedule_date_preference": call.get_field("reschedule_date_preference"),
        "reschedule_time_preference": call.get_field("reschedule_time_preference"),
        "loaner_car_needed": call.get_field("loaner_car_needed"),
        "additional_service_requests": call.get_field("additional_service_requests"),
        "decline_reason": call.get_field("decline_reason"),
        "callback_requested": call.get_field("callback_requested"),
        "callback_timeframe": call.get_field("callback_timeframe"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound service reminder call for Lakeside Auto Group"
    )
    parser.add_argument("phone", help="Customer phone number to call")
    parser.add_argument("--name", required=True, help="Customer full name")
    parser.add_argument(
        "--vehicle",
        required=True,
        help='Vehicle year, make, and model (e.g. "2021 Toyota Camry")',
    )
    parser.add_argument(
        "--service-type",
        default="oil change and tire rotation",
        help="Type of service due (default: oil change and tire rotation)",
    )
    parser.add_argument("--mileage", required=True, help="Current vehicle mileage")
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
            "vehicle": args.vehicle,
            "service_type": args.service_type,
            "mileage": args.mileage,
        },
    )

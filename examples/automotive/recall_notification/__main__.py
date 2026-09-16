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
    name="Quinn",
    organization="Lakeside Auto Group — Safety Team",
    purpose=(
        "notify vehicle owners about open safety recalls and collect their "
        "scheduling preferences so the required repair can be completed"
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
            f"Hi, this is Quinn from Lakeside Auto Group calling for "
            f"{call.get_variable('customer_name')} regarding an important vehicle "
            f"update. Please call us back at your earliest "
            f"convenience. Thank you."
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    customer_name = call.get_variable("customer_name")
    vehicle = call.get_variable("vehicle")
    recall_number = call.get_variable("recall_number")
    recall_description = call.get_variable("recall_description")
    recall_severity = call.get_variable("recall_severity")

    if outcome == "available":
        call.set_task(
            "recall_notification",
            objective=(
                f"Inform {customer_name} that their {vehicle} is affected by "
                f"safety recall {recall_number} ({recall_description}). "
                f"Confirm they are aware and verify they still have the vehicle. "
                f"The repair is free of charge."
            ),
            checklist=[
                guava.Say(
                    f"Explain that their {vehicle} has an open safety recall "
                    f"(Recall #{recall_number}) related to: "
                    f"{recall_description}. Emphasize that the repair is free "
                    f"of charge."
                ),
                guava.Field(
                    key="recall_acknowledged",
                    description="Whether the customer acknowledges being informed of the recall",
                    field_type="multiple_choice",
                    choices=["yes", "no"],
                    required=True,
                ),
                guava.Field(
                    key="vehicle_in_possession",
                    description="Whether the customer still owns or has access to the affected vehicle",
                    field_type="multiple_choice",
                    choices=["yes", "no"],
                    required=True,
                ),
            ],
        )
    elif outcome == "do_not_contact":
        logging.info("Customer %s requested no further contact.", customer_name)
        call.hangup(
            final_instructions=(
                "Acknowledge their request politely. Let them know they have been "
                "removed from our contact list and will not be called again. Note "
                "that for safety recalls, a written notice will still be mailed as "
                "required by law, and politely say goodbye."
            )
        )
    elif outcome == "wrong_number":
        logging.info("Wrong number reached for %s.", customer_name)
        call.hangup(final_instructions="Apologize for the mistake and wish them well, and politely say goodbye.")
    else:
        logging.info("Could not reach %s (outcome: %s).", customer_name, outcome)
        call.hangup()


@agent.on_task_complete("recall_notification")
def on_recall_notification_done(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    recall_severity = call.get_variable("recall_severity")

    if call.get_field("vehicle_in_possession") == "no":
        call.hangup(
            final_instructions=(
                f"Thank {customer_name} for letting us know they no longer have "
                f"the vehicle. Let them know we will update our records. "
                f"Wish them a good day, and politely say goodbye."
            )
        )
        return

    if recall_severity == "safety-critical":
        call.set_task(
            "urgent_scheduling",
            objective=(
                f"This is a safety-critical recall. Emphasize to {customer_name} "
                f"that this repair should be completed as soon as possible for their "
                f"safety and the safety of others. Help them schedule at the earliest "
                f"available date. The repair is free and typically takes 1-2 hours."
            ),
            checklist=[
                guava.Say(
                    f"Let {customer_name} know that this recall is classified as "
                    f"safety-critical, meaning the issue could affect the safe "
                    f"operation of the vehicle. Strongly encourage scheduling the "
                    f"repair as soon as possible."
                ),
                guava.Field(
                    key="appointment_date_preference",
                    description="The customer's preferred date for the recall repair — encourage the earliest available",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="transportation_needed",
                    description="Whether the customer needs transportation during the repair",
                    field_type="multiple_choice",
                    choices=["loaner car", "shuttle", "neither"],
                    required=True,
                ),
                guava.Field(
                    key="questions_about_recall",
                    description="Any questions or concerns the customer has about the recall or repair process",
                    field_type="text",
                    required=False,
                ),
            ],
        )
    else:
        call.set_task(
            "flexible_scheduling",
            objective=(
                f"This is a convenience recall for {customer_name}. The issue is "
                f"not safety-critical but should still be addressed. Help them find "
                f"a date that works with their schedule. The repair is free."
            ),
            checklist=[
                guava.Field(
                    key="appointment_date_preference",
                    description="The customer's preferred date for the recall repair",
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
                    key="transportation_needed",
                    description="Whether the customer needs transportation during the repair",
                    field_type="multiple_choice",
                    choices=["loaner car", "shuttle", "neither"],
                    required=True,
                ),
                guava.Field(
                    key="questions_about_recall",
                    description="Any questions or concerns the customer has about the recall or repair process",
                    field_type="text",
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("urgent_scheduling")
def on_urgent_scheduled(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    call.hangup(
        final_instructions=(
            f"Thank {customer_name} for prioritizing this important safety repair. "
            f"Confirm their appointment preference has been noted and that the "
            f"service team will reach out to confirm. Reassure them the repair is "
            f"straightforward and free of charge, and wish them a safe day, and politely say goodbye."
        )
    )


@agent.on_task_complete("flexible_scheduling")
def on_flexible_scheduled(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    call.hangup(
        final_instructions=(
            f"Thank {customer_name} for their time. Confirm their appointment "
            f"preference has been noted and that the service team will be in "
            f"touch with a confirmed time. The repair is completely free. "
            f"Wish them a pleasant day, and politely say goodbye."
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
            "contact list and won't be called again. Note that a written recall "
            "notice will still be mailed as required by law, and wish them well, and politely say goodbye."
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
        "recall_number": call.get_variable("recall_number"),
        "recall_description": call.get_variable("recall_description"),
        "recall_severity": call.get_variable("recall_severity"),
        "recall_acknowledged": call.get_field("recall_acknowledged"),
        "vehicle_in_possession": call.get_field("vehicle_in_possession"),
        "appointment_date_preference": call.get_field("appointment_date_preference"),
        "appointment_time_preference": call.get_field("appointment_time_preference"),
        "transportation_needed": call.get_field("transportation_needed"),
        "questions_about_recall": call.get_field("questions_about_recall"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound recall notification call for Lakeside Auto Group Safety Team"
    )
    parser.add_argument("phone", help="Customer phone number to call")
    parser.add_argument("--name", required=True, help="Customer full name")
    parser.add_argument(
        "--vehicle",
        required=True,
        help='Vehicle year, make, and model (e.g. "2021 Toyota Camry")',
    )
    parser.add_argument("--recall-number", required=True, help="NHTSA or manufacturer recall number")
    parser.add_argument(
        "--recall-description",
        required=True,
        help="Brief description of the recall and affected component",
    )
    parser.add_argument(
        "--recall-severity",
        default="safety-critical",
        choices=["safety-critical", "convenience"],
        help="Severity of the recall (default: safety-critical)",
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
            "customer_name": args.name,
            "vehicle": args.vehicle,
            "recall_number": args.recall_number,
            "recall_description": args.recall_description,
            "recall_severity": args.recall_severity,
        },
    )

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
    name="Drew",
    organization="Springfield Emergency Management",
    purpose=(
        "deliver an urgent emergency notification to residents, confirm "
        "acknowledgment, and connect those who need help to emergency services"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
    "connect_emergency_services": "The caller has an immediate emergency or needs to reach 9-1-1 or emergency responders",
})


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    alert_type = call.get_variable("alert_type")
    call.reach_person(
        contact_full_name=call.get_variable("resident_name"),
        voicemail_message=(
            f"IMPORTANT MESSAGE from Springfield Emergency Management. "
            f"There is currently a {alert_type} affecting your area. "
            f"{call.get_variable('instructions')}. "
            f"For updates, visit the Springfield Emergency Management website "
            f"or call 1-800-555-0300. This is a critical public safety alert."
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    resident_name = call.get_variable("resident_name")
    alert_type = call.get_variable("alert_type")
    instructions = call.get_variable("instructions")

    if outcome == "available":
        call.set_task(
            "notification",
            objective=(
                f"Deliver an urgent public safety alert regarding a {alert_type} "
                f"to {resident_name}. The instructions for residents are: "
                f"{instructions}. Deliver the alert clearly and calmly. Do not "
                f"cause unnecessary panic, but convey the seriousness of the "
                f"situation. Collect confirmation that the resident has received "
                f"the alert and determine if they need assistance."
            ),
            checklist=[
                guava.Say(
                    f"This is an important emergency notification. There is currently "
                    f"a {alert_type} affecting your area. {instructions}. "
                    f"Please listen carefully. I have a few brief questions to confirm "
                    f"you have received this alert and to determine if you need any "
                    f"assistance."
                ),
                guava.Field(
                    key="alert_acknowledged",
                    description=(
                        "Confirm that the resident has heard and understood the "
                        "emergency alert and the instructions provided"
                    ),
                    field_type="multiple_choice",
                    choices=["confirmed", "needs_clarification"],
                    required=True,
                ),
                guava.Field(
                    key="can_comply",
                    description=(
                        "Ask whether the resident is able to follow the emergency "
                        "instructions provided — for example, can they evacuate, "
                        "shelter in place, or take the recommended action"
                    ),
                    field_type="multiple_choice",
                    choices=["yes", "no", "needs_help"],
                    required=True,
                ),
            ],
        )
    elif outcome == "do_not_contact":
        logging.info("Resident %s requested no further contact.", resident_name)
        call.hangup(
            final_instructions=(
                "Acknowledge their request. Let them know they will not receive "
                "further phone calls, but strongly encourage them to monitor local "
                "emergency broadcasts for their safety, and politely say goodbye."
            )
        )
    elif outcome == "wrong_number":
        logging.info("Wrong number reached for %s.", resident_name)
        call.hangup(final_instructions="Apologize for the mistake and wish them well, and politely say goodbye.")
    else:
        logging.info("Could not reach %s (outcome: %s).", resident_name, outcome)
        call.hangup()


@agent.on_task_complete("notification")
def on_notification_done(call: guava.Call) -> None:
    can_comply = call.get_field("can_comply")
    resident_name = call.get_variable("resident_name")

    if can_comply == "needs_help":
        call.set_task(
            "assistance_needed",
            objective=(
                f"{resident_name} needs help complying with the emergency alert. "
                f"Determine what kind of assistance they need — evacuation transport, "
                f"medical assistance, shelter location, or something else. Collect "
                f"their address and specific needs so emergency services can be "
                f"dispatched. Assure them that help is on the way."
            ),
            checklist=[
                guava.Field(
                    key="household_members_count",
                    description=(
                        "How many people are currently in the household"
                    ),
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="special_needs_or_pets",
                    description=(
                        "Whether anyone in the household has special medical "
                        "needs, mobility limitations, or pets that would require "
                        "specific accommodations during evacuation or sheltering"
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="assistance_type",
                    description="What type of assistance the resident needs",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="current_address",
                    description="The resident's current address for emergency responders",
                    field_type="text",
                    required=True,
                ),
            ],
        )
    elif can_comply == "no":
        call.set_task(
            "cannot_comply",
            objective=(
                f"{resident_name} is unable to comply with the emergency "
                f"instructions. Find out why they cannot comply and offer "
                f"alternative actions they can take. If their situation requires "
                f"immediate help, note it for dispatch."
            ),
            checklist=[
                guava.Field(
                    key="household_members_count",
                    description=(
                        "How many people are currently in the household"
                    ),
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="special_needs_or_pets",
                    description=(
                        "Whether anyone in the household has special medical "
                        "needs, mobility limitations, or pets that would require "
                        "specific accommodations during evacuation or sheltering"
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="reason_cannot_comply",
                    description="Why the resident is unable to follow the emergency instructions",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="alternative_action",
                    description="Any alternative action the resident can take given their situation",
                    field_type="text",
                    required=False,
                ),
            ],
        )
    else:
        logging.info("Resident %s confirmed receipt of emergency alert.", resident_name)
        call.hangup(
            final_instructions=(
                f"Reiterate the most critical action {resident_name} should take. "
                f"Direct them to tune in to local emergency broadcasts or visit the "
                f"Springfield Emergency Management website for updates, and let "
                f"them go so they can take action, and politely say goodbye."
            )
        )


@agent.on_task_complete("assistance_needed")
def on_assistance_done(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            f"Assure {call.get_variable('resident_name')} that their information "
            f"has been noted and that emergency services are aware of their need. "
            f"Tell them to stay safe and await assistance. Provide the emergency "
            f"hotline number 1-800-555-0300 in case they need to call back, and politely say goodbye."
        )
    )


@agent.on_task_complete("cannot_comply")
def on_cannot_comply_done(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            f"Acknowledge {call.get_variable('resident_name')}'s situation. "
            f"Summarize any alternative actions discussed. Encourage them to stay "
            f"as safe as possible and call 9-1-1 if they are in immediate danger. "
            f"Provide the Springfield Emergency Management hotline 1-800-555-0300, and politely say goodbye."
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
            "Acknowledge their request. Let them know they will not receive further "
            "calls, but strongly encourage them to monitor emergency broadcasts for "
            "their own safety, and politely say goodbye."
        )
    )


@agent.on_action("connect_emergency_services")
def handle_emergency(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            "Let them know that for immediate emergencies they should call 9-1-1 "
            "directly. Provide the Springfield Emergency Management hotline at "
            "1-800-555-0300 for non-9-1-1 assistance, and let them go so they "
            "can dial 9-1-1 immediately, and politely say goodbye."
        )
    )


@agent.on_outbound_failed
def on_outbound_failed(event: OutboundCallFailed) -> None:
    logging.error("Outbound call failed: %s (code %d)", event.error_reason, event.error_code)


@agent.on_session_end
def on_session_end(call: guava.Call, event: BotSessionEnded) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "use_case": "emergency_notification",
        "resident_name": call.get_variable("resident_name"),
        "alert_type": call.get_variable("alert_type"),
        "alert_acknowledged": call.get_field("alert_acknowledged"),
        "can_comply": call.get_field("can_comply"),
        "household_members_count": call.get_field("household_members_count"),
        "special_needs_or_pets": call.get_field("special_needs_or_pets"),
        "assistance_type": call.get_field("assistance_type"),
        "current_address": call.get_field("current_address"),
        "reason_cannot_comply": call.get_field("reason_cannot_comply"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound emergency notification call for Springfield Emergency Management."
    )
    parser.add_argument("phone", help="Resident phone number to call (E.164 format).")
    parser.add_argument("--name", required=True, help="Full name of the resident.")
    parser.add_argument(
        "--alert-type",
        required=True,
        help='Type of emergency alert (e.g., "tornado warning", "flash flood warning").',
    )
    parser.add_argument(
        "--instructions",
        required=True,
        help="Specific instructions for residents to follow in response to the alert.",
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
            "alert_type": args.alert_type,
            "instructions": args.instructions,
        },
    )

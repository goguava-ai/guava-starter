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
    name="Harper",
    organization="The Grand Meridian Hotel",
    purpose=(
        "reach out to guests ahead of their arrival to collect preferences "
        "and special requests so the hotel team can prepare a personalized stay"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
    "speak_to_someone": "The caller wants to speak to the concierge, front desk, or a real person",
})


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(
        contact_full_name=call.get_variable("guest_name"),
        voicemail_message=(
            f"Hi, this is Harper from The Grand Meridian Hotel calling for "
            f"{call.get_variable('guest_name')}. We're looking forward to your "
            f"upcoming stay and wanted to see if there's anything we can prepare "
            f"for you. Please call us back at your convenience. Thank you!"
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    guest_name = call.get_variable("guest_name")
    checkin_date = call.get_variable("checkin_date")
    reservation_number = call.get_variable("reservation_number")

    if outcome == "available":
        call.set_task(
            "pre_arrival",
            objective=(
                f"Call {guest_name} ahead of their check-in on {checkin_date} "
                f"(reservation {reservation_number}). Collect any special "
                f"requests so the hotel team can prepare. Ask about dietary "
                f"restrictions, accessibility needs, and early check-in "
                f"preferences. Be warm and genuine — make the guest feel valued "
                f"before they even arrive."
            ),
            checklist=[
                guava.Say(
                    f"We're excited to welcome you on {checkin_date} and I "
                    f"wanted to reach out to see if there's anything we can "
                    f"prepare for your arrival."
                ),
                guava.Field(
                    key="dietary_restrictions",
                    description=(
                        "Any dietary restrictions, allergies, or food preferences "
                        "the hotel should be aware of for dining"
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="accessibility_needs",
                    description=(
                        "Any accessibility accommodations needed, such as "
                        "wheelchair access, grab bars, or roll-in shower"
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="early_checkin",
                    description=(
                        "Whether the guest would like to request early check-in. "
                        "If yes, note that early check-in is subject to availability "
                        "and the hotel will do its best to accommodate."
                    ),
                    field_type="multiple_choice",
                    choices=["yes", "no"],
                    required=True,
                ),
                guava.Field(
                    key="estimated_arrival_time",
                    description="What time the guest expects to arrive at the hotel",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="special_requests",
                    description=(
                        "Any other special requests or personal touches the guest "
                        "would like arranged, such as a celebration setup, extra "
                        "pillows, or specific room features"
                    ),
                    field_type="text",
                    required=False,
                ),
            ],
        )
    elif outcome == "do_not_contact":
        logging.info("Guest %s requested no further contact.", guest_name)
        call.hangup(
            final_instructions=(
                "Acknowledge their request graciously. Let them know they will "
                "not be contacted again, and wish them well, and politely say goodbye."
            )
        )
    elif outcome == "wrong_number":
        logging.info("Wrong number for %s.", guest_name)
        call.hangup(final_instructions="Apologize for the mistake and wish them well, and politely say goodbye.")
    else:
        logging.info("Could not reach %s (outcome: %s).", guest_name, outcome)
        call.hangup()


@agent.on_task_complete("pre_arrival")
def on_pre_arrival_done(call: guava.Call) -> None:
    guest_name = call.get_variable("guest_name")
    dietary = call.get_field("dietary_restrictions")
    accessibility = call.get_field("accessibility_needs")
    early = call.get_field("early_checkin")

    # Branch on special requests collected
    if dietary and str(dietary).strip():
        logging.info("Dietary preferences noted for %s: %s", guest_name, dietary)

    if accessibility and str(accessibility).strip():
        logging.info("Accessibility needs noted for %s: %s", guest_name, accessibility)

    if early == "yes":
        call.hangup(
            final_instructions=(
                f"Thank {guest_name} for sharing their preferences. Let them "
                f"know the hotel will do its best to accommodate early check-in "
                f"and they will receive a confirmation message the evening before "
                f"arrival. Let them know everything will be prepared and the team "
                f"is looking forward to welcoming them, and wish them a pleasant journey, and politely say goodbye."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {guest_name} graciously for taking the time to share "
                f"their preferences. Let them know the hotel team will have "
                f"everything ready upon arrival. Express how much the team is "
                f"looking forward to welcoming them, and wish them a pleasant journey, and politely say goodbye."
            )
        )


@agent.on_action_request
def on_action_request(call: guava.Call, intent_summary: str):
    return _mid_call_intent.classify(intent_summary)


@agent.on_action("do_not_contact")
def handle_dnc(call: guava.Call) -> None:
    logging.info("Guest %s requested DNC mid-call.", call.get_variable("guest_name"))
    call.hangup(
        final_instructions=(
            "Acknowledge their request. Let them know they have been removed "
            "from the contact list and will not be called again, and wish them well, and politely say goodbye."
        )
    )


@agent.on_action("speak_to_someone")
def handle_speak_to_someone(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            "Let them know that a member of the concierge team will call them "
            "back within one business day. Ask if there is a preferred time "
            "and thank them, and politely say goodbye."
        )
    )


@agent.on_outbound_failed
def on_outbound_failed(event: OutboundCallFailed) -> None:
    logging.error("Outbound call failed: %s (code %d)", event.error_reason, event.error_code)


@agent.on_session_end
def on_session_end(call: guava.Call, event: BotSessionEnded) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "use_case": "pre_arrival",
        "guest_name": call.get_variable("guest_name"),
        "reservation_number": call.get_variable("reservation_number"),
        "checkin_date": call.get_variable("checkin_date"),
        "dietary_restrictions": call.get_field("dietary_restrictions"),
        "accessibility_needs": call.get_field("accessibility_needs"),
        "early_checkin": call.get_field("early_checkin"),
        "estimated_arrival_time": call.get_field("estimated_arrival_time"),
        "special_requests": call.get_field("special_requests"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound pre-arrival preferences call — The Grand Meridian Hotel"
    )
    parser.add_argument("phone", help="Guest phone number to call")
    parser.add_argument("--name", required=True, help="Full name of the guest")
    parser.add_argument("--reservation-number", required=True, help="Reservation reference number")
    parser.add_argument("--checkin-date", required=True, help="Scheduled check-in date")
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
            "guest_name": args.name,
            "reservation_number": args.reservation_number,
            "checkin_date": args.checkin_date,
        },
    )

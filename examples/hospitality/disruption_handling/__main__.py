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

SUPPORT_LINE = "+18005550190"


# ---------------------------------------------------------------------------
# Mock API — simulates alternative availability lookup
# ---------------------------------------------------------------------------

MOCK_DISRUPTIONS = {
    "BK-77200": {
        "traveler": "Priya Sharma",
        "original_flight": "MT-4021 (LAX to JFK, Aug 10 at 8:00 AM)",
        "disruption_type": "weather",
        "disruption_detail": "Severe thunderstorms in the New York area",
        "alternatives": [
            {"flight": "MT-4025", "route": "LAX to JFK", "departs": "Aug 10 at 2:30 PM"},
            {"flight": "MT-4033", "route": "LAX to JFK", "departs": "Aug 11 at 7:00 AM"},
            {"flight": "MT-4040", "route": "LAX to EWR", "departs": "Aug 10 at 4:00 PM"},
        ],
    },
    "BK-77201": {
        "traveler": "Daniel Fischer",
        "original_flight": "MT-2100 (ORD to SFO, Aug 12 at 11:00 AM)",
        "disruption_type": "mechanical",
        "disruption_detail": "Aircraft maintenance issue requiring part replacement",
        "alternatives": [
            {"flight": "MT-2104", "route": "ORD to SFO", "departs": "Aug 12 at 3:15 PM"},
            {"flight": "MT-2108", "route": "ORD to SFO", "departs": "Aug 12 at 6:00 PM"},
        ],
    },
    "BK-77202": {
        "traveler": "Megan O'Brien",
        "original_flight": "MT-6500 (MIA to DEN, Aug 14 at 9:00 AM)",
        "disruption_type": "schedule_change",
        "disruption_detail": "Route schedule adjustment effective August 2026",
        "alternatives": [
            {"flight": "MT-6502", "route": "MIA to DEN", "departs": "Aug 14 at 11:30 AM"},
            {"flight": "MT-6510", "route": "MIA to DEN", "departs": "Aug 14 at 2:00 PM"},
            {"flight": "MT-6520", "route": "MIA to DEN", "departs": "Aug 15 at 9:00 AM"},
        ],
    },
}


def lookup_disruption(booking_ref):
    return MOCK_DISRUPTIONS.get(booking_ref)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

agent = guava.Agent(
    name="Alex",
    organization="Meridian Travel Services",
    purpose=(
        "proactively contact travelers affected by flight disruptions, explain "
        "the situation, present rebooking options, and confirm new arrangements"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
    "speak_to_support": "The caller wants to speak to a support agent, supervisor, or live person",
})


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(
        contact_full_name=call.get_variable("traveler_name"),
        voicemail_message=(
            f"Hi, this is Alex from Meridian Travel Services calling for "
            f"{call.get_variable('traveler_name')} regarding an important update "
            f"to your upcoming travel. Please call us back at 1-800-555-0190 "
            f"as soon as possible. Thank you."
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    traveler_name = call.get_variable("traveler_name")
    booking_ref = call.get_variable("booking_reference")

    if outcome == "available":
        disruption = lookup_disruption(booking_ref)

        if disruption is None:
            logging.warning("Booking %s not found.", booking_ref)
            call.hangup(
                final_instructions=(
                    "Apologize and let them know you were unable to locate their "
                    "booking. Suggest they contact support at 1-800-555-0190, and politely say goodbye."
                )
            )
            return

        call.set_variable("disruption_type", disruption["disruption_type"])
        alt_summary = "; ".join(
            f"{a['flight']} — {a['route']}, {a['departs']}"
            for a in disruption["alternatives"]
        )

        call.add_info("disruption_details", {
            "booking_reference": booking_ref,
            "original_flight": disruption["original_flight"],
            "disruption_type": disruption["disruption_type"],
            "disruption_detail": disruption["disruption_detail"],
            "alternatives": alt_summary,
        })

        call.set_task(
            "notify_disruption",
            objective=(
                f"Notify {traveler_name} that their flight "
                f"{disruption['original_flight']} has been disrupted due to "
                f"{disruption['disruption_detail']}. Explain the situation "
                f"clearly, empathize with the inconvenience, and confirm they "
                f"understand before moving to rebooking options."
            ),
            checklist=[
                guava.Say(
                    "I'm reaching out with an important update about your "
                    "upcoming flight."
                ),
                guava.Field(
                    key="disruption_acknowledged",
                    description=(
                        "Whether the traveler has acknowledged and understood "
                        "the disruption notification"
                    ),
                    field_type="text",
                    required=True,
                ),
            ],
        )
    elif outcome == "do_not_contact":
        logging.info("Traveler %s requested no further contact.", traveler_name)
        call.hangup(
            final_instructions=(
                "Acknowledge their request. Let them know they will not be "
                "contacted again. Note that important travel updates will be "
                "sent via email instead, and politely say goodbye."
            )
        )
    elif outcome == "wrong_number":
        logging.info("Wrong number for %s.", traveler_name)
        call.hangup(final_instructions="Apologize for the mistake and wish them well, and politely say goodbye.")
    else:
        logging.info("Could not reach %s (outcome: %s).", traveler_name, outcome)
        call.hangup()


@agent.on_task_complete("notify_disruption")
def on_disruption_notified(call: guava.Call) -> None:
    traveler_name = call.get_variable("traveler_name")
    disruption_type = call.get_variable("disruption_type")

    if disruption_type == "weather":
        compensation_note = (
            "Because this disruption is weather-related, a full refund is "
            "available if none of the alternatives work. "
        )
    elif disruption_type == "mechanical":
        compensation_note = (
            "Because this is a mechanical issue, Meridian Travel Services will "
            "provide a travel credit as compensation in addition to rebooking. "
        )
    else:
        compensation_note = ""

    call.set_task(
        "present_options",
        objective=(
            f"Present the available rebooking options to {traveler_name}. "
            f"{compensation_note}"
            f"Share the alternatives from the disruption details and help them "
            f"choose the best option. If none of the options work, offer to "
            f"transfer to support for additional help."
        ),
        checklist=[
            guava.Field(
                key="rebooking_preference",
                description=(
                    "Which alternative the traveler prefers, or whether they "
                    "want a refund or to speak to support"
                ),
                field_type="text",
                required=True,
            ),
        ],
    )


@agent.on_task_complete("present_options")
def on_options_presented(call: guava.Call) -> None:
    traveler_name = call.get_variable("traveler_name")
    preference = (call.get_field("rebooking_preference") or "").lower()

    if "refund" in preference or "support" in preference or "none" in preference:
        call.transfer(
            destination=SUPPORT_LINE,
            instructions=(
                f"{traveler_name} needs additional help with their disrupted "
                f"booking. Connect them with the support team. Let them know "
                f"all information has been saved."
            ),
        )
    else:
        call.set_task(
            "confirm_arrangement",
            objective=(
                f"Confirm the new travel arrangement with {traveler_name}. "
                f"Read back the selected option and collect their email for "
                f"confirmation details."
            ),
            checklist=[
                guava.Field(
                    key="arrangement_confirmed",
                    description="Whether the traveler confirms the new flight arrangement",
                    field_type="multiple_choice",
                    choices=["yes", "no"],
                    required=True,
                ),
                guava.Field(
                    key="seat_preference",
                    description="Any seat preference for the rebooked flight (window, aisle, etc.)",
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="confirmation_email",
                    description="Email address to send the new booking confirmation to",
                    field_type="text",
                    required=True,
                ),
            ],
        )


@agent.on_task_complete("confirm_arrangement")
def on_arrangement_confirmed(call: guava.Call) -> None:
    traveler_name = call.get_variable("traveler_name")
    confirmed = call.get_field("arrangement_confirmed")

    if confirmed == "no":
        call.transfer(
            destination=SUPPORT_LINE,
            instructions=(
                f"{traveler_name} was not satisfied with the options. Connect "
                f"them with support for further assistance."
            ),
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {traveler_name} for their patience and understanding. "
                f"Confirm that the new booking confirmation will be sent to the "
                f"email provided. Let them know they can reach Meridian Travel "
                f"Services at 1-800-555-0190 for any questions. Wish them safe "
                f"travels, and politely say goodbye."
            )
        )


@agent.on_action_request
def on_action_request(call: guava.Call, intent_summary: str):
    return _mid_call_intent.classify(intent_summary)


@agent.on_action("do_not_contact")
def handle_dnc(call: guava.Call) -> None:
    logging.info("Traveler %s requested DNC mid-call.", call.get_variable("traveler_name"))
    call.hangup(
        final_instructions=(
            "Acknowledge their request. Let them know they will not be contacted "
            "again by phone and that updates will be sent by email, and wish them well, and politely say goodbye."
        )
    )


@agent.on_action("speak_to_support")
def handle_support_transfer(call: guava.Call) -> None:
    call.transfer(
        destination=SUPPORT_LINE,
        instructions=(
            "Let them know you are connecting them with a support representative "
            "now. Reassure them that their booking information has been saved."
        ),
    )


@agent.on_outbound_failed
def on_outbound_failed(event: OutboundCallFailed) -> None:
    logging.error("Outbound call failed: %s (code %d)", event.error_reason, event.error_code)


@agent.on_session_end
def on_session_end(call: guava.Call, event: BotSessionEnded) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "use_case": "disruption_handling",
        "traveler_name": call.get_variable("traveler_name"),
        "booking_reference": call.get_variable("booking_reference"),
        "disruption_type": call.get_variable("disruption_type"),
        "disruption_acknowledged": call.get_field("disruption_acknowledged"),
        "rebooking_preference": call.get_field("rebooking_preference"),
        "seat_preference": call.get_field("seat_preference"),
        "arrangement_confirmed": call.get_field("arrangement_confirmed"),
        "confirmation_email": call.get_field("confirmation_email"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound flight disruption handling call — Meridian Travel Services"
    )
    parser.add_argument("phone", help="Traveler phone number to call")
    parser.add_argument("--name", required=True, help="Full name of the traveler")
    parser.add_argument(
        "--booking-reference",
        required=True,
        help="Booking reference (try BK-77200, BK-77201, or BK-77202)",
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
            "traveler_name": args.name,
            "booking_reference": args.booking_reference,
        },
    )

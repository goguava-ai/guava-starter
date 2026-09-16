# SDK conformance: guava-sdk 0.44.0 (2026-09-15)
import argparse
import json
import logging
import os
from datetime import datetime, timezone

import guava
from guava import logging_utils
from guava.helpers.llm import IntentRecognizer
from guava.events import BotSessionEnded, OutboundCallFailed

RESERVATIONS_LINE = "+15551000800"


# ---------------------------------------------------------------------------
# Mock API — simulates reservation lookup
# ---------------------------------------------------------------------------

MOCK_RESERVATIONS = {
    "RES-55100": {
        "guest": "Catherine Ellis",
        "room_type": "Ocean View Suite",
        "original_dates": "August 15-18, 2026",
        "nightly_rate": 389,
        "cancellation_reason": None,
        "loyalty_tier": "Gold",
    },
    "RES-55101": {
        "guest": "Michael Chen",
        "room_type": "Deluxe King",
        "original_dates": "September 5-8, 2026",
        "nightly_rate": 275,
        "cancellation_reason": None,
        "loyalty_tier": None,
    },
    "RES-55102": {
        "guest": "Aisha Patel",
        "room_type": "Garden View Double",
        "original_dates": "August 22-25, 2026",
        "nightly_rate": 210,
        "cancellation_reason": None,
        "loyalty_tier": "Silver",
    },
}


def lookup_reservation(reservation_number):
    return MOCK_RESERVATIONS.get(reservation_number)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

agent = guava.Agent(
    name="Sophie",
    organization="The Grand Meridian Hotel",
    purpose=(
        "reach out to guests who recently cancelled a reservation, understand "
        "the reason with empathy, explore whether alternative arrangements "
        "might address their concerns, and warmly invite them to rebook"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
    "speak_to_reservations": "The caller wants to speak to the reservations team or a real person",
})


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_persona(
        organization_name="The Grand Meridian Hotel",
        agent_name="Sophie",
        agent_purpose=(
            "reach out to guests who recently cancelled a reservation with "
            "empathy, care, and zero pressure"
        ),
    )
    call.reach_person(
        contact_full_name=call.get_variable("guest_name"),
        voicemail_message=(
            f"Hi, this is Sophie from The Grand Meridian Hotel calling for "
            f"{call.get_variable('guest_name')}. We noticed a recent change to "
            f"your reservation and wanted to see if there's anything we can do "
            f"to help. Please call us back at your convenience. Thank you!"
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    guest_name = call.get_variable("guest_name")
    reservation_number = call.get_variable("reservation_number")

    if outcome == "available":
        reservation = lookup_reservation(reservation_number)

        if reservation is None:
            logging.warning("Reservation %s not found.", reservation_number)
            call.hangup(
                final_instructions=(
                    "Apologize for the inconvenience and let them know you were "
                    "unable to locate the reservation. Suggest they contact the "
                    "reservations team directly, and politely say goodbye."
                )
            )
            return

        call.add_info("reservation_details", {
            "reservation_number": reservation_number,
            "room_type": reservation["room_type"],
            "original_dates": reservation["original_dates"],
            "loyalty_tier": reservation["loyalty_tier"],
        })

        call.set_task(
            "understand_cancellation",
            objective=(
                f"Call {guest_name} about the cancellation of reservation "
                f"{reservation_number} for a {reservation['room_type']} on "
                f"{reservation['original_dates']}. Approach with genuine care "
                f"and zero pressure. Understand why they cancelled, then "
                f"thoughtfully explore alternatives. Respect their decision — "
                f"if they decline, do not push after one attempt."
            ),
            checklist=[
                guava.Say(
                    f"I noticed your reservation for "
                    f"{reservation['original_dates']} was recently cancelled, "
                    f"and I just wanted to reach out to see if everything is okay."
                ),
                guava.Field(
                    key="cancellation_reason",
                    description=(
                        "The primary reason the guest cancelled. Listen carefully "
                        "and capture their response in full."
                    ),
                    field_type="text",
                    required=True,
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


@agent.on_task_complete("understand_cancellation")
def on_cancellation_understood(call: guava.Call) -> None:
    guest_name = call.get_variable("guest_name")
    reason = call.get_field("cancellation_reason") or ""
    reason_lower = reason.lower()

    # Classify cancellation reason and branch
    if any(word in reason_lower for word in ["date", "schedule", "timing", "conflict", "can't make"]):
        call.set_task(
            "offer_alternative",
            objective=(
                f"The guest's dates don't work. Ask if they would be open to "
                f"rebooking for different dates, and if so, what dates would "
                f"work better. Do not look up or suggest specific availability "
                f"— simply collect their preferences. If they are not interested "
                f"after one attempt, gracefully close."
            ),
            checklist=[
                guava.Field(
                    key="open_to_new_dates",
                    description="Whether the guest is open to rebooking for different dates",
                    field_type="multiple_choice",
                    choices=["yes", "no", "maybe"],
                    required=True,
                ),
                guava.Field(
                    key="preferred_dates",
                    description="If open to rebooking, what dates would work better for the guest",
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="rebooking_decision",
                    description="The guest's final decision on rebooking",
                    field_type="multiple_choice",
                    choices=["rebook", "think_about_it", "not_interested"],
                    required=True,
                ),
            ],
        )
    elif any(word in reason_lower for word in ["price", "expensive", "cost", "budget", "afford"]):
        call.set_task(
            "offer_alternative",
            objective=(
                f"The guest cancelled due to cost concerns. Let them know you "
                f"can pass their feedback to the reservations team, who may be "
                f"able to offer alternative options. Ask if they would like "
                f"someone from the reservations team to follow up — offer "
                f"once, and if they decline, respect their decision without "
                f"pressure."
            ),
            checklist=[
                guava.Field(
                    key="discount_interest",
                    description=(
                        "Whether the guest would like the reservations team to "
                        "follow up with alternative options"
                    ),
                    field_type="multiple_choice",
                    choices=["yes", "no", "tell_me_more"],
                    required=True,
                ),
                guava.Field(
                    key="rebooking_decision",
                    description="The guest's final decision on rebooking",
                    field_type="multiple_choice",
                    choices=["rebook", "think_about_it", "not_interested"],
                    required=True,
                ),
            ],
        )
    else:
        # Found alternative or personal reasons — graceful close
        call.set_task(
            "offer_alternative",
            objective=(
                f"The guest cancelled for personal reasons or found an "
                f"alternative. Acknowledge their decision with warmth. Ask if "
                f"there is anything The Grand Meridian could do differently in "
                f"the future. Do NOT pressure them to rebook."
            ),
            checklist=[
                guava.Field(
                    key="feedback",
                    description=(
                        "Any feedback the guest would like to share about what "
                        "might bring them back to The Grand Meridian in the future"
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="rebooking_decision",
                    description="The guest's current stance on a future stay",
                    field_type="multiple_choice",
                    choices=["rebook", "think_about_it", "not_interested"],
                    required=True,
                ),
            ],
        )


@agent.on_task_complete("offer_alternative")
def on_alternative_offered(call: guava.Call) -> None:
    guest_name = call.get_variable("guest_name")
    decision = call.get_field("rebooking_decision")

    if decision == "rebook":
        call.transfer(
            destination=RESERVATIONS_LINE,
            instructions=(
                f"{guest_name} would like to rebook. Connect them with the "
                f"reservations team to finalize the new booking. Share that "
                f"they are a returning guest so the team can offer the best "
                f"available options."
            ),
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {guest_name} warmly for their time and for speaking "
                f"openly. Leave the door open for a future stay without any "
                f"pressure. Wish them well and let them know The Grand Meridian "
                f"would love to welcome them anytime, and politely say goodbye."
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
            "Acknowledge their request graciously. Let them know they will not "
            "be contacted again, and wish them well, and politely say goodbye."
        )
    )


@agent.on_action("speak_to_reservations")
def handle_reservations_transfer(call: guava.Call) -> None:
    call.transfer(
        destination=RESERVATIONS_LINE,
        instructions=(
            "Let them know you are connecting them with the reservations team "
            "now, and wish them a pleasant experience."
        ),
    )


@agent.on_outbound_failed
def on_outbound_failed(event: OutboundCallFailed) -> None:
    logging.error("Outbound call failed: %s (code %d)", event.error_reason, event.error_code)


@agent.on_session_end
def on_session_end(call: guava.Call, event: BotSessionEnded) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "use_case": "cancellation_winback",
        "guest_name": call.get_variable("guest_name"),
        "reservation_number": call.get_variable("reservation_number"),
        "cancellation_reason": call.get_field("cancellation_reason"),
        "rebooking_decision": call.get_field("rebooking_decision"),
        "open_to_new_dates": call.get_field("open_to_new_dates"),
        "preferred_dates": call.get_field("preferred_dates"),
        "discount_interest": call.get_field("discount_interest"),
        "feedback": call.get_field("feedback"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound cancellation winback call — The Grand Meridian Hotel"
    )
    parser.add_argument("phone", help="Guest phone number to call")
    parser.add_argument("--name", required=True, help="Full name of the guest")
    parser.add_argument(
        "--reservation-number",
        required=True,
        help="Cancelled reservation number (try RES-55100, RES-55101, or RES-55102)",
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
            "guest_name": args.name,
            "reservation_number": args.reservation_number,
        },
    )

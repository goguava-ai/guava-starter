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
    name="Ellis",
    organization="SwiftShip Logistics",
    purpose=(
        "confirm delivery receipt with recipients, identify missing or "
        "undelivered packages, and escalate unresolved deliveries for "
        "investigation"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
    "speak_to_support": "The caller wants to speak to a customer support agent or live person",
})


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(
        contact_full_name=call.get_variable("recipient_name"),
        voicemail_message=(
            f"Hi, this is Ellis from SwiftShip Logistics calling for "
            f"{call.get_variable('recipient_name')} regarding a recent delivery — "
            f"tracking number {call.get_variable('tracking_number')}. We're calling "
            f"to confirm receipt. Please call us back at your convenience or visit "
            f"the SwiftShip website. Thank you!"
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    recipient_name = call.get_variable("recipient_name")
    tracking_number = call.get_variable("tracking_number")
    delivery_date = call.get_variable("delivery_date")

    if outcome == "available":
        call.set_task(
            "confirm_delivery",
            objective=(
                f"Confirm with {recipient_name} whether they received the delivery "
                f"for tracking number {tracking_number}, which was marked as delivered "
                f"on {delivery_date}. Determine the acknowledgment status."
            ),
            checklist=[
                guava.Say(
                    f"I'm calling to confirm your delivery — tracking number "
                    f"{tracking_number}, which our records show was delivered on "
                    f"{delivery_date}."
                ),
                guava.Field(
                    key="delivery_acknowledgment",
                    description="Whether the recipient confirms they received the delivery",
                    field_type="multiple_choice",
                    choices=["confirmed_received", "not_received", "partial"],
                    required=True,
                ),
            ],
        )
    elif outcome == "do_not_contact":
        logging.info("Recipient %s requested no further contact.", recipient_name)
        call.hangup(
            final_instructions=(
                "Acknowledge their request. Let them know they have been removed from "
                "the delivery confirmation call list and will not be contacted again, and politely say goodbye."
            )
        )
    elif outcome == "wrong_number":
        logging.info("Wrong number reached for %s.", recipient_name)
        call.hangup(final_instructions="Apologize for the mistake and wish them well, and politely say goodbye.")
    else:
        logging.info("Could not reach %s (outcome: %s).", recipient_name, outcome)
        call.hangup()


@agent.on_task_complete("confirm_delivery")
def on_delivery_confirmed(call: guava.Call) -> None:
    acknowledgment = call.get_field("delivery_acknowledgment")
    recipient_name = call.get_variable("recipient_name")

    if acknowledgment == "confirmed_received":
        call.hangup(
            final_instructions=(
                f"Thank {recipient_name} for confirming receipt. Let them know that "
                f"the delivery has been marked as complete in our system. If they have "
                f"any questions about future deliveries, they can visit the SwiftShip "
                f"website, and wish them a great day, and politely say goodbye."
            )
        )
    elif acknowledgment == "not_received":
        call.set_task(
            "file_investigation",
            objective=(
                f"{recipient_name} reports they did not receive the delivery for "
                f"tracking number {call.get_variable('tracking_number')}. Collect "
                f"details to open an investigation. Be empathetic and assure them "
                f"SwiftShip will look into this."
            ),
            checklist=[
                guava.Field(
                    key="delivery_location_checked",
                    description=(
                        "Whether the recipient has checked common delivery locations "
                        "(front door, side entrance, mailroom, neighbor, etc.)"
                    ),
                    field_type="multiple_choice",
                    choices=["yes", "no"],
                    required=True,
                ),
                guava.Field(
                    key="anyone_else_received",
                    description=(
                        "Whether anyone else at the address may have received the package "
                        "(roommate, family member, building staff)"
                    ),
                    field_type="multiple_choice",
                    choices=["yes", "no", "not sure"],
                    required=True,
                ),
                guava.Field(
                    key="callback_number",
                    description="The best phone number to reach the recipient for investigation updates",
                    field_type="text",
                    required=True,
                ),
            ],
        )
    else:
        call.set_task(
            "collect_partial_details",
            objective=(
                f"{recipient_name} reports only a partial delivery for tracking number "
                f"{call.get_variable('tracking_number')}. Collect details about what "
                f"was received and what is missing so SwiftShip can follow up."
            ),
            checklist=[
                guava.Field(
                    key="items_received",
                    description="What items or parts of the shipment the recipient did receive",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="items_missing",
                    description="What items or parts of the shipment are missing",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="callback_number",
                    description="The best phone number to reach the recipient for follow-up",
                    field_type="text",
                    required=True,
                ),
            ],
        )


@agent.on_task_complete("file_investigation")
def on_investigation_filed(call: guava.Call) -> None:
    recipient_name = call.get_variable("recipient_name")
    call.hangup(
        final_instructions=(
            f"Let {recipient_name} know that an investigation has been opened "
            f"for their missing delivery. A SwiftShip support specialist will "
            f"follow up within 1 to 2 business days with an update. Thank them "
            f"for their patience and apologize for the inconvenience, and politely say goodbye."
        )
    )


@agent.on_task_complete("collect_partial_details")
def on_partial_details_done(call: guava.Call) -> None:
    recipient_name = call.get_variable("recipient_name")
    call.hangup(
        final_instructions=(
            f"Thank {recipient_name} for providing the details. Let them know "
            f"SwiftShip will investigate the missing items and follow up within "
            f"2 business days at the callback number provided. Apologize for the "
            f"inconvenience and wish them a good day, and politely say goodbye."
        )
    )


@agent.on_action_request
def on_action_request(call: guava.Call, intent_summary: str):
    return _mid_call_intent.classify(intent_summary)


@agent.on_action("do_not_contact")
def handle_dnc(call: guava.Call) -> None:
    logging.info("Recipient %s requested DNC mid-call.", call.get_variable("recipient_name"))
    call.hangup(
        final_instructions=(
            "Acknowledge their request. Let them know they've been removed from "
            "the call list and won't be contacted again, and wish them well, and politely say goodbye."
        )
    )


@agent.on_action("speak_to_support")
def handle_speak_to_support(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            "Let them know that a SwiftShip support specialist will call them back "
            "within one business day. Ask if there is a preferred time and thank them, and politely say goodbye."
        )
    )


@agent.on_outbound_failed
def on_outbound_failed(event: OutboundCallFailed) -> None:
    logging.error("Outbound call failed: %s (code %d)", event.error_reason, event.error_code)


@agent.on_session_end
def on_session_end(call: guava.Call, event: BotSessionEnded) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "recipient_name": call.get_variable("recipient_name"),
        "tracking_number": call.get_variable("tracking_number"),
        "delivery_date": call.get_variable("delivery_date"),
        "delivery_acknowledgment": call.get_field("delivery_acknowledgment"),
        "delivery_location_checked": call.get_field("delivery_location_checked"),
        "anyone_else_received": call.get_field("anyone_else_received"),
        "items_received": call.get_field("items_received"),
        "items_missing": call.get_field("items_missing"),
        "callback_number": call.get_field("callback_number"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound delivery confirmation call for SwiftShip Logistics"
    )
    parser.add_argument("phone", help="Recipient phone number to call")
    parser.add_argument("--name", required=True, help="Full name of the recipient")
    parser.add_argument("--tracking-number", required=True, help="Shipment tracking number")
    parser.add_argument("--delivery-date", required=True, help="Date the delivery was marked as completed")
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
            "recipient_name": args.name,
            "tracking_number": args.tracking_number,
            "delivery_date": args.delivery_date,
        },
    )

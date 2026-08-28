# SDK conformance: guava-sdk 0.40.0 (2026-08-26)
import argparse
import json
import logging
import os
from datetime import datetime, timezone

import guava
from guava import logging_utils
from guava.helpers.llm import DatetimeFilter, IntentRecognizer
from guava.events import BotSessionEnded, OutboundCallFailed


# ---------------------------------------------------------------------------
# Mock API — simulates a showing calendar backend for demo purposes
# ---------------------------------------------------------------------------

MOCK_SHOWING_SLOTS: dict[str, list[str]] = {
    "450 Main St, Unit 12": [
        "2026-07-28T10:00:00",
        "2026-07-28T14:00:00",
        "2026-07-29T15:00:00",
        "2026-07-30T10:00:00",
    ],
    "2201 Sunset Blvd": [
        "2026-07-28T09:00:00",
        "2026-07-29T10:00:00",
        "2026-07-30T14:00:00",
    ],
    "310 Ridgeview Dr": [
        "2026-07-29T11:00:00",
        "2026-07-30T09:00:00",
        "2026-07-31T15:00:00",
    ],
}


def book_showing(property_address, date, time_slot):
    confirmation = f"SHW-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}"
    logging.info(
        "[MOCK API] POST /showings — booked %s at %s on %s %s",
        confirmation, property_address, date, time_slot,
    )
    return confirmation


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

agent = guava.Agent(
    name="Blake",
    organization="Acme Realty Group",
    purpose=(
        "schedule property showings for interested buyers by confirming interest, "
        "searching available time slots, handling scheduling conflicts, and "
        "confirming the booking"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
    "speak_to_agent": "The caller wants to speak to a real estate agent or live person",
})


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(
        contact_full_name=call.get_variable("contact_name"),
        voicemail_message=(
            f"Hi, this is Blake from Acme Realty Group calling for "
            f"{call.get_variable('contact_name')} about scheduling a showing at "
            f"{call.get_variable('property_address')}. We have some great times "
            f"available! Please call us back at your convenience to get a tour "
            f"set up. Thank you!"
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    contact_name = call.get_variable("contact_name")
    property_address = call.get_variable("property_address")

    if outcome == "available":
        call.set_task(
            "confirm_interest",
            objective=(
                f"Confirm that {contact_name} is still interested in seeing "
                f"{property_address} before proceeding with scheduling."
            ),
            checklist=[
                guava.Say(
                    f"I'm calling about scheduling a showing at {property_address}. "
                    f"We'd love to set up a tour for you!"
                ),
                guava.Field(
                    key="still_interested",
                    description="Whether the buyer is still interested in seeing this property",
                    field_type="multiple_choice",
                    choices=["yes", "no"],
                    required=True,
                ),
            ],
        )
    elif outcome == "do_not_contact":
        logging.info("Buyer %s requested no further contact.", contact_name)
        call.hangup(
            final_instructions=(
                "Acknowledge their request. Let them know they will not be contacted "
                "again, and wish them well in their home search, and politely say goodbye."
            )
        )
    elif outcome == "wrong_number":
        logging.info("Wrong number reached for %s.", contact_name)
        call.hangup(final_instructions="Apologize for the mistake and wish them well, and politely say goodbye.")
    else:
        logging.info("Could not reach %s (outcome: %s).", contact_name, outcome)
        call.hangup()


@agent.on_task_complete("confirm_interest")
def on_interest_confirmed(call: guava.Call) -> None:
    interested = call.get_field("still_interested")
    contact_name = call.get_variable("contact_name")

    if interested != "yes":
        call.hangup(
            final_instructions=(
                f"Thank {contact_name} for letting you know. Let them know that "
                f"if they change their mind or want to see other properties, they "
                f"can call Acme Realty Group anytime, and wish them well, and politely say goodbye."
            )
        )
        return

    property_address = call.get_variable("property_address")
    call.set_task(
        "select_time",
        objective=(
            f"{contact_name} is interested in seeing {property_address}. "
            f"Collect their preferred date and time so we can find an available "
            f"showing slot."
        ),
        checklist=[
            guava.Field(
                key="preferred_time",
                description=(
                    f"The buyer's preferred date and time for touring {property_address}. "
                    f"Ask for a specific date and whether morning, afternoon, or "
                    f"evening works best."
                ),
                field_type="text",
                required=True,
                searchable=True,
            ),
        ],
    )


@agent.on_search_query("preferred_time")
def search_preferred_time(call: guava.Call, query: str):
    property_address = call.get_variable("property_address")
    slots = MOCK_SHOWING_SLOTS.get(property_address, [])
    datetime_filter = DatetimeFilter(source_list=slots)
    return datetime_filter.filter(query, max_results=3)


@agent.on_task_complete("select_time")
def on_time_selected(call: guava.Call) -> None:
    preferred = call.get_field("preferred_time")
    property_address = call.get_variable("property_address")
    contact_name = call.get_variable("contact_name")

    if preferred:
        parts = preferred.split(" ", 1)
        date_str = parts[0] if parts else preferred
        time_str = parts[1] if len(parts) > 1 else ""
        confirmation = book_showing(property_address, date_str, time_str)
        call.set_variable("confirmation_number", confirmation)

        call.set_task(
            "confirm_booking",
            objective=(
                f"Showing booked! Confirmation number {confirmation} for "
                f"{contact_name} at {property_address} on {preferred}. "
                f"Confirm the details and ask about additional properties."
            ),
            checklist=[
                guava.Say(
                    f"You're all set! I've booked your showing at "
                    f"{property_address} for {preferred}. Your confirmation "
                    f"number is {confirmation}."
                ),
                guava.Field(
                    key="additional_properties",
                    description=(
                        "Whether the buyer wants to schedule showings for any "
                        "other properties during the same visit"
                    ),
                    field_type="text",
                    required=False,
                ),
            ],
        )
    else:
        call.hangup(
            final_instructions=(
                f"Let {contact_name} know that we weren't able to find a slot "
                f"matching their preference right now. Suggest they call back or "
                f"check pinnaclerealtygroup.com for updated availability. An agent "
                f"can also help find alternative dates or properties, and politely say goodbye."
            )
        )


@agent.on_task_complete("confirm_booking")
def on_booking_confirmed(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    call.hangup(
        final_instructions=(
            f"Confirm the showing details back to {contact_name} — the property "
            f"address, date, and time. Let them know they'll receive a calendar "
            f"confirmation and a reminder the day before. If they mentioned "
            f"additional properties, let them know an agent will follow up to "
            f"coordinate. Thank them and wish them an exciting home search, and politely say goodbye."
        )
    )


@agent.on_action_request
def on_action_request(call: guava.Call, intent_summary: str):
    return _mid_call_intent.classify(intent_summary)


@agent.on_action("do_not_contact")
def handle_dnc(call: guava.Call) -> None:
    logging.info("Buyer %s requested DNC mid-call.", call.get_variable("contact_name"))
    call.hangup(
        final_instructions=(
            "Acknowledge their request. Let them know they've been removed from "
            "the call list and won't be contacted again, and wish them well, and politely say goodbye."
        )
    )


@agent.on_action("speak_to_agent")
def handle_speak_to_agent(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            "Let them know that a Acme Realty Group agent will call them back "
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
        "use_case": "showing_scheduling",
        "contact_name": call.get_variable("contact_name"),
        "property_address": call.get_variable("property_address"),
        "still_interested": call.get_field("still_interested"),
        "preferred_time": call.get_field("preferred_time"),
        "confirmation_number": call.get_variable("confirmation_number"),
        "additional_properties": call.get_field("additional_properties"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound showing scheduling call for Acme Realty Group"
    )
    parser.add_argument("phone", help="The buyer's phone number to call")
    parser.add_argument("--name", required=True, help="Full name of the buyer to reach")
    parser.add_argument(
        "--property-address",
        default="the property you inquired about",
        help="Address or description of the property to be shown",
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
            "property_address": args.property_address,
        },
    )

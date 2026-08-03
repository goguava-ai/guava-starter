# SDK conformance: guava-sdk 0.35.0 (2026-07-21)
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
    name="Riley",
    organization="Lakeside Auto Group — Finance",
    purpose=(
        "contact lessees approaching the end of their lease term to discuss "
        "their options — returning the vehicle, purchasing it, or re-leasing — "
        "and collect their decision so the finance team can prepare accordingly"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
    "speak_to_someone": "The caller wants to speak to a real person, a manager, or the finance team",
})


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(
        contact_full_name=call.get_variable("customer_name"),
        voicemail_message=(
            f"Hi, this is Riley from Lakeside Auto Group calling for "
            f"{call.get_variable('customer_name')}. We're reaching out regarding "
            f"your vehicle lease. Please call us back at your convenience. Thank you!"
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    customer_name = call.get_variable("customer_name")
    vehicle = call.get_variable("vehicle")
    lease_end_date = call.get_variable("lease_end_date")
    buyout_price = call.get_variable("buyout_price")

    if outcome == "available":
        call.set_task(
            "lease_end_outreach",
            objective=(
                f"Reach out to {customer_name} whose lease on their {vehicle} "
                f"ends on {lease_end_date}. Walk them through the three options: "
                f"returning the vehicle, buying it out (buyout price: {buyout_price}), "
                f"or re-leasing a new vehicle. Collect their decision."
            ),
            checklist=[
                guava.Say(
                    f"Let {customer_name} know that their lease on the {vehicle} "
                    f"is ending on {lease_end_date} and walk them through their "
                    f"options: returning the vehicle, purchasing it for "
                    f"{buyout_price}, or re-leasing a new model."
                ),
                guava.Field(
                    key="lease_end_decision",
                    description="The customer's current decision or preference for their lease-end option.",
                    field_type="multiple_choice",
                    choices=["return the vehicle", "buy it out", "re-lease a new vehicle", "undecided"],
                    required=True,
                ),
            ],
        )
    elif outcome == "do_not_contact":
        logging.info("Customer %s requested no further contact.", customer_name)
        call.hangup(
            final_instructions=(
                "Acknowledge their request politely. Let them know they have been "
                "removed from our follow-up list and will not be contacted again, and politely say goodbye."
            )
        )
    elif outcome == "wrong_number":
        logging.info("Wrong number reached for %s.", customer_name)
        call.hangup(final_instructions="Apologize for the mistake and wish them well, and politely say goodbye.")
    else:
        logging.info("Could not reach %s (outcome: %s).", customer_name, outcome)
        call.hangup()


@agent.on_task_complete("lease_end_outreach")
def on_lease_end_outreach_done(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    decision = call.get_field("lease_end_decision")

    if decision == "return the vehicle":
        call.set_task(
            "schedule_inspection",
            objective=(
                f"{customer_name} wants to return the vehicle. Schedule a pre-return "
                f"inspection at Lakeside Auto Group. Explain that an inspection is "
                f"required before the lease-end date to assess the vehicle condition "
                f"and finalize the return."
            ),
            checklist=[
                guava.Field(
                    key="inspection_date_preference",
                    description="The customer's preferred date for the pre-return vehicle inspection",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="inspection_time_preference",
                    description="The customer's preferred time of day for the inspection (morning, afternoon, or specific time)",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="new_vehicle_interest",
                    description="Whether the customer is interested in exploring new vehicle options at the dealership",
                    field_type="multiple_choice",
                    choices=["yes", "no", "maybe later"],
                    required=True,
                ),
            ],
        )
    elif decision == "buy it out":
        call.set_task(
            "buyout_confirmation",
            objective=(
                f"{customer_name} wants to purchase their leased vehicle. Confirm "
                f"they understand the buyout price and let them know you will "
                f"connect them with the finance team to start the paperwork."
            ),
            checklist=[
                guava.Field(
                    key="buyout_price_confirmed",
                    description="Whether the customer confirms they understand and accept the buyout price",
                    field_type="multiple_choice",
                    choices=["yes", "wants more info"],
                    required=True,
                ),
                guava.Field(
                    key="financing_needed",
                    description="Whether the customer needs financing for the buyout or plans to pay in full",
                    field_type="multiple_choice",
                    choices=["needs financing", "paying in full", "not sure yet"],
                    required=True,
                ),
            ],
        )
    elif decision == "re-lease a new vehicle":
        call.set_task(
            "schedule_dealership_visit",
            objective=(
                f"{customer_name} wants to re-lease a new vehicle. Collect their "
                f"preferences and schedule a visit to Lakeside Auto Group to explore "
                f"new models."
            ),
            checklist=[
                guava.Field(
                    key="re_lease_model_preference",
                    description="The make, model, or vehicle type the customer is interested in for their next lease",
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="visit_date_preference",
                    description="The customer's preferred date to visit the dealership",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="visit_time_preference",
                    description="The customer's preferred time to visit the dealership (morning, afternoon, or specific time)",
                    field_type="text",
                    required=True,
                ),
            ],
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {customer_name} for their time. Let them know a member of "
                f"the Lakeside Auto Group finance team will follow up as their "
                f"lease-end date approaches. Encourage them to call back anytime "
                f"once they've decided, and wish them a great day, and politely say goodbye."
            )
        )


@agent.on_task_complete("schedule_inspection")
def on_inspection_scheduled(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    call.hangup(
        final_instructions=(
            f"Thank {customer_name} for scheduling the inspection. Confirm "
            f"their preferred date and time have been noted and that the service "
            f"team will reach out to confirm, and wish them a great day, and politely say goodbye."
        )
    )


@agent.on_task_complete("buyout_confirmation")
def on_buyout_confirmed(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    call.hangup(
        final_instructions=(
            f"Thank {customer_name} for their interest in purchasing the vehicle. "
            f"Let them know the finance team will reach out within one business day "
            f"to walk them through the buyout paperwork, and wish them a great day, and politely say goodbye."
        )
    )


@agent.on_task_complete("schedule_dealership_visit")
def on_visit_scheduled(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    call.hangup(
        final_instructions=(
            f"Thank {customer_name} for their time. Confirm their dealership visit "
            f"preference has been noted and that a sales consultant will be in touch "
            f"to confirm, and wish them a great day, and politely say goodbye."
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
            "Let them know that someone from the Lakeside Auto Group finance team "
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
        "lease_end_date": call.get_variable("lease_end_date"),
        "buyout_price": call.get_variable("buyout_price"),
        "lease_end_decision": call.get_field("lease_end_decision"),
        "inspection_date_preference": call.get_field("inspection_date_preference"),
        "inspection_time_preference": call.get_field("inspection_time_preference"),
        "buyout_price_confirmed": call.get_field("buyout_price_confirmed"),
        "financing_needed": call.get_field("financing_needed"),
        "re_lease_model_preference": call.get_field("re_lease_model_preference"),
        "visit_date_preference": call.get_field("visit_date_preference"),
        "visit_time_preference": call.get_field("visit_time_preference"),
        "new_vehicle_interest": call.get_field("new_vehicle_interest"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound lease-end outreach call for Lakeside Auto Group Finance"
    )
    parser.add_argument("phone", help="Customer phone number to call")
    parser.add_argument("--name", required=True, help="Customer full name")
    parser.add_argument(
        "--vehicle",
        required=True,
        help='Vehicle year, make, and model (e.g. "2021 Toyota Camry")',
    )
    parser.add_argument("--lease-end-date", required=True, help="Date the lease term ends")
    parser.add_argument(
        "--buyout-price",
        default="available upon request",
        help="Vehicle buyout price (default: available upon request)",
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
            "lease_end_date": args.lease_end_date,
            "buyout_price": args.buyout_price,
        },
    )

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
    name="Jamie",
    organization="Lakeside Auto Group",
    purpose=(
        "follow up with customers after a service visit to confirm their "
        "satisfaction, address any unresolved concerns, and invite them to "
        "leave a review"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
    "speak_to_someone": "The caller wants to speak to a real person, a manager, or the service department",
})


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(
        contact_full_name=call.get_variable("customer_name"),
        voicemail_message=(
            f"Hi, this is Jamie from Lakeside Auto Group calling for "
            f"{call.get_variable('customer_name')}. We're reaching out to check in "
            f"after your recent service visit. No action is needed — feel free to "
            f"call us back at your convenience. Thank you!"
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    customer_name = call.get_variable("customer_name")
    vehicle = call.get_variable("vehicle")
    service_date = call.get_variable("service_date")
    service_performed = call.get_variable("service_performed")

    if outcome == "available":
        call.set_task(
            "followup",
            objective=(
                f"Follow up with {customer_name} regarding their {vehicle} "
                f"that was serviced on {service_date} for {service_performed}. "
                f"Confirm they are satisfied with the work, check that the vehicle is "
                f"performing well, and address any outstanding concerns."
            ),
            checklist=[
                guava.Say(
                    f"Thank {customer_name} for coming in and mention their "
                    f"recent visit on {service_date} for {service_performed} "
                    f"on their {vehicle}."
                ),
                guava.Field(
                    key="satisfaction_rating",
                    description=(
                        "Customer's overall satisfaction rating for the service visit, "
                        "on a scale of 1 to 5 where 1 is very unsatisfied and 5 is very satisfied"
                    ),
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="vehicle_performing_well",
                    description="Whether the vehicle has been performing well since the service visit",
                    field_type="multiple_choice",
                    choices=["yes", "no", "not sure"],
                    required=True,
                ),
                guava.Field(
                    key="additional_concerns",
                    description="Any additional concerns or issues the customer wants to mention",
                    field_type="text",
                    required=False,
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


@agent.on_task_complete("followup")
def on_followup_done(call: guava.Call) -> None:
    rating = call.get_field("satisfaction_rating")
    customer_name = call.get_variable("customer_name")

    if rating is not None and rating <= 2:
        call.set_task(
            "low_satisfaction_followup",
            objective=(
                f"{customer_name} gave a low satisfaction rating ({rating}/5). "
                f"Ask what specifically went wrong and what Lakeside Auto Group could "
                f"have done better. Listen carefully and be empathetic. Let them know "
                f"the service manager will personally review their feedback."
            ),
            checklist=[
                guava.Field(
                    key="dissatisfaction_reason",
                    description="What specifically the customer was unhappy about",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="wants_manager_callback",
                    description="Whether the customer would like a callback from the service manager",
                    field_type="multiple_choice",
                    choices=["yes", "no"],
                    required=True,
                ),
            ],
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {customer_name} sincerely for their feedback and for choosing "
                f"Lakeside Auto Group. Let them know we'd love for them to share their "
                f"experience with a quick online review — a link will be texted to them. "
                f"Wish them a wonderful day, and politely say goodbye."
            )
        )


@agent.on_task_complete("low_satisfaction_followup")
def on_low_satisfaction_done(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    call.hangup(
        final_instructions=(
            f"Thank {customer_name} for sharing that feedback — it genuinely helps. "
            f"Assure them that their concerns will be reviewed by the service manager. "
            f"If they requested a callback, confirm that the manager will reach out "
            f"within one business day, and wish them a good day, and politely say goodbye."
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
        "service_date": call.get_variable("service_date"),
        "service_performed": call.get_variable("service_performed"),
        "satisfaction_rating": call.get_field("satisfaction_rating"),
        "vehicle_performing_well": call.get_field("vehicle_performing_well"),
        "additional_concerns": call.get_field("additional_concerns"),
        "dissatisfaction_reason": call.get_field("dissatisfaction_reason"),
        "wants_manager_callback": call.get_field("wants_manager_callback"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound post-service follow-up call for Lakeside Auto Group"
    )
    parser.add_argument("phone", help="Customer phone number to call")
    parser.add_argument("--name", required=True, help="Customer full name")
    parser.add_argument(
        "--vehicle",
        required=True,
        help='Vehicle year, make, and model (e.g. "2021 Toyota Camry")',
    )
    parser.add_argument("--service-date", required=True, help="Date of the service visit")
    parser.add_argument(
        "--service-performed",
        default="your recent service",
        help="Description of the service performed (default: your recent service)",
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
            "service_date": args.service_date,
            "service_performed": args.service_performed,
        },
    )

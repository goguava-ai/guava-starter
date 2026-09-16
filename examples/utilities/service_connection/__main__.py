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


# ---------------------------------------------------------------------------
# Mock API — simulates a service scheduling backend for demo purposes
# ---------------------------------------------------------------------------

SCHEDULING_LINE = "+15551000600"

MOCK_APPLICATIONS = {
    "APP-220101": {
        "name": "Sarah Martinez",
        "dob": "1988-05-12",
        "service_address": "742 Evergreen Terrace, Springfield",
        "available_dates": ["August 4, 2026", "August 5, 2026", "August 7, 2026"],
        "time_windows": ["Morning (8 AM to 12 PM)", "Afternoon (12 PM to 5 PM)"],
    },
    "APP-220245": {
        "name": "Michael Brooks",
        "dob": "1995-01-28",
        "service_address": "1024 Oak Avenue, Springfield",
        "available_dates": ["August 6, 2026", "August 8, 2026", "August 11, 2026"],
        "time_windows": ["Morning (8 AM to 12 PM)", "Afternoon (12 PM to 5 PM)"],
    },
    "APP-220389": {
        "name": "Jennifer Patel",
        "dob": "1972-08-19",
        "service_address": "315 Maple Drive, Springfield",
        "available_dates": ["August 5, 2026", "August 12, 2026"],
        "time_windows": ["Afternoon (12 PM to 5 PM)"],
    },
}


def verify_application(application_number, dob):
    app = MOCK_APPLICATIONS.get(application_number)
    if app and app["dob"] == dob:
        return app
    return None


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

agent = guava.Agent(
    name="Finley",
    organization="Metro Power & Light — New Connections",
    purpose=(
        "verify customer identity, confirm service address details, schedule "
        "a service connection appointment, and collect access instructions "
        "for the technician"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
    "speak_to_someone": "The caller wants to speak to a scheduling representative or customer service agent",
})


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(
        contact_full_name=call.get_variable("contact_name"),
        voicemail_message=(
            f"Hi, this is Finley from Metro Power & Light New Connections "
            f"calling for {call.get_variable('contact_name')}. We're calling to "
            f"schedule your electric service activation. Please call us back at "
            f"your convenience. Thank you."
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    contact_name = call.get_variable("contact_name")

    if outcome == "available":
        call.set_task(
            "verify_identity",
            objective=(
                f"Verify the identity of {contact_name} before discussing their "
                f"service application. Ask for their date of birth. Do not share "
                f"address details or scheduling information until identity is "
                f"confirmed."
            ),
            checklist=[
                guava.Say(
                    f"I'm calling about your application to start electric "
                    f"service. Before we proceed, I need to verify your identity "
                    f"with a quick question."
                ),
                guava.Field(
                    key="dob",
                    description="The applicant's date of birth for identity verification",
                    field_type="text",
                    required=True,
                ),
            ],
        )
    elif outcome == "do_not_contact":
        logging.info("Customer %s requested no further contact.", contact_name)
        call.hangup(
            final_instructions=(
                "Acknowledge their request. Let them know they will not be contacted "
                "again by phone. Suggest they visit metropowerandlight.com to "
                "schedule their service connection online, and politely say goodbye."
            )
        )
    elif outcome == "wrong_number":
        logging.info("Wrong number for %s.", contact_name)
        call.hangup(final_instructions="Apologize for the mistake and wish them well, and politely say goodbye.")
    else:
        logging.info("Could not reach %s (outcome: %s).", contact_name, outcome)
        call.hangup()


@agent.on_task_complete("verify_identity")
def on_identity_verified(call: guava.Call) -> None:
    application_number = call.get_variable("application_number")
    dob = call.get_field("dob")
    app = verify_application(application_number, dob)

    if app is None:
        logging.warning("Identity verification failed for application %s.", application_number)
        call.hangup(
            final_instructions=(
                "Let them know the date of birth provided does not match our records "
                "for this application. For security, you cannot proceed. Suggest they "
                "call Metro Power & Light at the main customer service line with their "
                "application documents handy, and politely say goodbye."
            )
        )
        return

    contact_name = call.get_variable("contact_name")
    call.set_variable("service_address", app["service_address"])
    call.set_variable("available_dates", ", ".join(app["available_dates"]))

    call.add_info("application_details", {
        "application_number": application_number,
        "service_address": app["service_address"],
        "available_dates": app["available_dates"],
        "time_windows": app["time_windows"],
    })

    call.set_task(
        "confirm_address",
        objective=(
            f"Identity verified — the customer is {contact_name}. Confirm the "
            f"service address on file is {app['service_address']}."
        ),
        checklist=[
            guava.Say(
                f"Thank you, {contact_name}. Your identity has been verified. "
                f"I see your application is for service at {app['service_address']}. "
                f"Let's get your connection appointment scheduled."
            ),
            guava.Field(
                key="address_confirmed",
                description="Whether the customer confirms the service address is correct",
                field_type="multiple_choice",
                choices=["yes", "no"],
                required=True,
            ),
        ],
    )


@agent.on_task_complete("confirm_address")
def on_address_confirmed(call: guava.Call) -> None:
    address_confirmed = call.get_field("address_confirmed")
    contact_name = call.get_variable("contact_name")

    if address_confirmed == "no":
        call.transfer(
            destination=SCHEDULING_LINE,
            instructions=(
                f"The service address on file does not match what {contact_name} "
                f"expected. Transfer them to the scheduling team to update the "
                f"address and reschedule. Let them know their information so far "
                f"has been saved."
            ),
        )
        return

    app_num = call.get_variable("application_number")
    app = MOCK_APPLICATIONS.get(app_num, {})
    available_dates = app.get("available_dates", [])
    time_windows = app.get("time_windows", [])

    call.set_task(
        "schedule_connection",
        objective=(
            f"The address is confirmed. Now schedule the service connection "
            f"appointment. Available dates are: {', '.join(available_dates)}. "
            f"Available time windows are: {', '.join(time_windows)}. If the "
            f"customer's preferred date is not available, offer the closest "
            f"alternatives."
        ),
        checklist=[
            guava.Field(
                key="move_in_date",
                description="What date the customer is planning to move in",
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="preferred_connection_date",
                description=(
                    "Which available date the customer would like for their "
                    "service activation"
                ),
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="preferred_time_window",
                description="Which time window works best for the customer",
                field_type="multiple_choice",
                choices=["Morning (8 AM to 12 PM)", "Afternoon (12 PM to 5 PM)", "Any time"],
                required=True,
            ),
        ],
    )


@agent.on_task_complete("schedule_connection")
def on_date_confirmed(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")

    call.set_task(
        "collect_access_info",
        objective=(
            f"The connection date has been selected. Now collect access "
            f"instructions that the technician will need on installation day. "
            f"Also offer optional programs like autopay and paperless billing."
        ),
        checklist=[
            guava.Field(
                key="gate_code_or_access_notes",
                description=(
                    "Any gate code, lockbox code, or special access instructions "
                    "the technician will need to reach the meter"
                ),
                field_type="text",
                required=False,
            ),
            guava.Field(
                key="someone_present",
                description=(
                    "Whether someone 18 or older will be present at the property "
                    "during the scheduled time window"
                ),
                field_type="multiple_choice",
                choices=["yes", "no"],
                required=True,
            ),
            guava.Field(
                key="billing_address_confirmed",
                description=(
                    "Whether the billing address is the same as the service "
                    "address or if they have a different mailing address"
                ),
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="autopay_interest",
                description=(
                    "Whether the customer would like to enroll in autopay for "
                    "a small monthly discount"
                ),
                field_type="text",
                required=False,
            ),
        ],
    )


@agent.on_task_complete("collect_access_info")
def on_access_collected(call: guava.Call) -> None:
    someone_present = call.get_field("someone_present")
    contact_name = call.get_variable("contact_name")

    if someone_present == "no":
        call.hangup(
            final_instructions=(
                f"Let {contact_name} know that someone 18 or older must be present "
                f"at the property during the scheduled window for the technician to "
                f"activate service. Ask if they'd like to reschedule to a time when "
                f"someone can be present, or if they can arrange for another adult "
                f"to be there. They can call 1-555-100-0600 to reschedule. A confirmation "
                f"will be sent by email or text, and politely say goodbye."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Confirm the connection appointment details with {contact_name}: "
                f"the date, time window, and service address. Let them know a "
                f"technician will arrive during the scheduled window and that a "
                f"confirmation will be sent by email or text. Welcome them to "
                f"Metro Power & Light and wish them well with their move, and politely say goodbye."
            )
        )


@agent.on_action_request
def on_action_request(call: guava.Call, intent_summary: str):
    return _mid_call_intent.classify(intent_summary)


@agent.on_action("do_not_contact")
def handle_dnc(call: guava.Call) -> None:
    logging.info("Customer %s requested DNC mid-call.", call.get_variable("contact_name"))
    call.hangup(
        final_instructions=(
            "Acknowledge their request. Let them know they will not be contacted "
            "again by phone. Suggest scheduling online at metropowerandlight.com. "
            "Wish them well, and politely say goodbye."
        )
    )


@agent.on_action("speak_to_someone")
def handle_transfer_request(call: guava.Call) -> None:
    call.transfer(
        destination=SCHEDULING_LINE,
        instructions="Let them know you're connecting them with a scheduling representative now.",
    )


@agent.on_outbound_failed
def on_outbound_failed(event: OutboundCallFailed) -> None:
    logging.error("Outbound call failed: %s (code %d)", event.error_reason, event.error_code)


@agent.on_session_end
def on_session_end(call: guava.Call, event: BotSessionEnded) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "use_case": "service_connection",
        "contact_name": call.get_variable("contact_name"),
        "application_number": call.get_variable("application_number"),
        "service_address": call.get_variable("service_address"),
        "dob_verified": call.get_field("dob") is not None,
        "address_confirmed": call.get_field("address_confirmed"),
        "move_in_date": call.get_field("move_in_date"),
        "preferred_connection_date": call.get_field("preferred_connection_date"),
        "preferred_time_window": call.get_field("preferred_time_window"),
        "gate_code_or_access_notes": call.get_field("gate_code_or_access_notes"),
        "someone_present": call.get_field("someone_present"),
        "billing_address_confirmed": call.get_field("billing_address_confirmed"),
        "autopay_interest": call.get_field("autopay_interest"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Metro Power & Light New Connections — Service Activation Scheduling"
    )
    parser.add_argument("phone", help="Customer phone number to call")
    parser.add_argument("--name", required=True, help="Customer full name")
    parser.add_argument(
        "--application-number",
        required=True,
        help="New service application number (try APP-220101, APP-220245, or APP-220389)",
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
            "application_number": args.application_number,
        },
    )

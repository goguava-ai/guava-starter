# SDK conformance: guava-sdk 0.38.0 (2026-08-11)
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
    name="Lane",
    organization="Metro Power & Light",
    purpose=(
        "explain the benefits of the smart meter upgrade program to eligible "
        "customers, address concerns, and schedule installation for those who "
        "wish to enroll"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
    "speak_to_someone": "The caller wants to speak to a representative or customer service agent",
})


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(
        contact_full_name=call.get_variable("contact_name"),
        voicemail_message=(
            f"Hi, this is Lane from Metro Power & Light calling for "
            f"{call.get_variable('contact_name')}. Your home is eligible for a "
            f"free smart meter upgrade. Please call us back at your convenience "
            f"to learn more. Thank you."
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    contact_name = call.get_variable("contact_name")
    account_number = call.get_variable("account_number")

    if outcome == "available":
        call.set_task(
            "smart_meter_enrollment",
            objective=(
                f"Speak with {contact_name} (account {account_number}) about "
                f"enrolling in the Metro Power & Light smart meter upgrade program. "
                f"Explain that smart meters provide real-time usage data, eliminate "
                f"estimated bills, enable remote meter reading, and unlock access "
                f"to energy usage tools. Determine the customer's interest level."
            ),
            checklist=[
                guava.Say(
                    f"I'm calling about an upgrade available for your account. "
                    f"Your home is eligible for our free smart meter installation. "
                    f"Smart meters give you real-time visibility into your energy "
                    f"usage, eliminate estimated bills, and mean our technicians "
                    f"no longer need to access your property for monthly readings. "
                    f"The installation takes about 30 minutes and is completely "
                    f"free of charge."
                ),
                guava.Field(
                    key="interest_level",
                    description=(
                        "Ask whether the customer would like to enroll and schedule "
                        "an installation, has concerns they'd like addressed first, "
                        "or would prefer to decline at this time"
                    ),
                    field_type="multiple_choice",
                    choices=["enroll", "has_concerns", "decline"],
                    required=True,
                ),
            ],
        )
    elif outcome == "do_not_contact":
        logging.info("Customer %s requested no further contact.", contact_name)
        call.hangup(
            final_instructions=(
                "Acknowledge their request. Let them know they will not be "
                "contacted again about the smart meter program, and politely say goodbye."
            )
        )
    elif outcome == "wrong_number":
        logging.info("Wrong number reached for %s.", contact_name)
        call.hangup(final_instructions="Apologize for the mistake and wish them well, and politely say goodbye.")
    else:
        logging.info("Could not reach %s (outcome: %s).", contact_name, outcome)
        call.hangup()


@agent.on_task_complete("smart_meter_enrollment")
def on_enrollment_done(call: guava.Call) -> None:
    interest = call.get_field("interest_level")
    contact_name = call.get_variable("contact_name")

    if interest == "enroll":
        call.set_task(
            "schedule_installation",
            objective=(
                f"{contact_name} wants to enroll in the smart meter program. "
                f"Collect their scheduling preferences for the installation "
                f"appointment."
            ),
            checklist=[
                guava.Field(
                    key="installation_date_preference",
                    description="What date works best for the smart meter installation",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="installation_window_preference",
                    description="Preferred installation time window",
                    field_type="multiple_choice",
                    choices=["Morning (8 AM to 12 PM)", "Afternoon (12 PM to 5 PM)", "Any time"],
                    required=True,
                ),
            ],
        )
    elif interest == "has_concerns":
        call.set_task(
            "address_concerns",
            objective=(
                f"{contact_name} has concerns about the smart meter program. "
                f"Listen to their specific concerns and address common objections: "
                f"smart meters are safe and meet all FCC standards, data is "
                f"encrypted and protected, there is no cost for installation, "
                f"and the meter does not affect home insurance. Be patient and "
                f"informative without being pushy."
            ),
            checklist=[
                guava.Field(
                    key="specific_concerns",
                    description="What specific concerns the customer has about smart meters",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="concerns_addressed",
                    description=(
                        "Whether the customer feels their concerns were adequately "
                        "addressed and if they would now like to enroll"
                    ),
                    field_type="multiple_choice",
                    choices=["ready_to_enroll", "still_undecided", "prefers_to_decline"],
                    required=True,
                ),
            ],
        )
    else:
        # decline
        call.hangup(
            final_instructions=(
                f"Thank {contact_name} for their time. Let them know the offer "
                f"remains available and they can enroll anytime by calling Metro "
                f"Power & Light or visiting metropowerandlight.com. Wish them "
                f"a good day, and politely say goodbye."
            )
        )


@agent.on_task_complete("schedule_installation")
def on_schedule_done(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    call.set_task(
        "collect_access_info",
        objective=(
            f"The installation date is set. Collect any access instructions "
            f"the technician will need on installation day."
        ),
        checklist=[
            guava.Field(
                key="pets_to_secure",
                description=(
                    "Whether the customer has pets that need to be secured "
                    "on installation day"
                ),
                field_type="text",
                required=False,
            ),
            guava.Field(
                key="gate_code_or_access_notes",
                description=(
                    "Any gate code or special access instructions the "
                    "technician will need to reach the meter"
                ),
                field_type="text",
                required=False,
            ),
        ],
    )


@agent.on_task_complete("collect_access_info")
def on_access_done(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            f"Confirm the appointment details with {call.get_variable('contact_name')}, "
            f"including the date and time window. Let them know a technician will "
            f"call 30 minutes before arriving and someone 18 or older must be "
            f"present. A confirmation will be sent by email or text. Thank them "
            f"for choosing to upgrade, and politely say goodbye."
        )
    )


@agent.on_task_complete("address_concerns")
def on_concerns_done(call: guava.Call) -> None:
    decision = call.get_field("concerns_addressed")
    contact_name = call.get_variable("contact_name")

    if decision == "ready_to_enroll":
        call.set_task(
            "schedule_installation",
            objective=(
                f"{contact_name} is now ready to enroll after having their concerns "
                f"addressed. Collect their scheduling preferences for installation."
            ),
            checklist=[
                guava.Field(
                    key="installation_date_preference",
                    description="What date works best for the smart meter installation",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="installation_window_preference",
                    description="Preferred installation time window",
                    field_type="multiple_choice",
                    choices=["Morning (8 AM to 12 PM)", "Afternoon (12 PM to 5 PM)", "Any time"],
                    required=True,
                ),
                guava.Field(
                    key="pets_to_secure",
                    description="Whether the customer has pets that need to be secured on installation day",
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="gate_code_or_access_notes",
                    description="Any gate code or special access instructions for the technician",
                    field_type="text",
                    required=False,
                ),
            ],
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {contact_name} for taking the time to learn about the "
                f"program. Let them know the offer remains open and they can "
                f"enroll anytime by contacting Metro Power & Light. Wish them "
                f"a good day, and politely say goodbye."
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
            "again about the smart meter program, and wish them well, and politely say goodbye."
        )
    )


@agent.on_action("speak_to_someone")
def handle_speak_to_someone(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            "Let them know that a Metro Power & Light representative will call "
            "them back within one business day. Ask if there's a preferred time "
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
        "use_case": "smart_meter_enrollment",
        "contact_name": call.get_variable("contact_name"),
        "account_number": call.get_variable("account_number"),
        "interest_level": call.get_field("interest_level"),
        "specific_concerns": call.get_field("specific_concerns"),
        "concerns_addressed": call.get_field("concerns_addressed"),
        "installation_date_preference": call.get_field("installation_date_preference"),
        "installation_window_preference": call.get_field("installation_window_preference"),
        "pets_to_secure": call.get_field("pets_to_secure"),
        "gate_code_or_access_notes": call.get_field("gate_code_or_access_notes"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Metro Power & Light — Smart Meter Enrollment Outbound Call"
    )
    parser.add_argument("phone", help="Customer phone number to call")
    parser.add_argument("--name", required=True, help="Customer full name")
    parser.add_argument("--account-number", required=True, help="Customer account number")
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
            "account_number": args.account_number,
        },
    )

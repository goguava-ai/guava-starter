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
    name="Alex",
    organization="Westfield University — Alumni Relations",
    purpose=(
        "engage alumni in meaningful conversation about giving back to the "
        "university and capture gift pledges and preferences to support "
        "future students"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
    "speak_to_someone": "The caller wants to speak to a real person in Alumni Relations or a manager",
})


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(
        contact_full_name=call.get_variable("name"),
        voicemail_message=(
            f"Hi, this is Alex from Westfield University Alumni Relations "
            f"calling for {call.get_variable('name')}. We'd love to reconnect "
            f"with you. Please call us back at your convenience. Thank you!"
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    alumni_name = call.get_variable("name")
    graduation_year = call.get_variable("graduation_year")
    major = call.get_variable("major")

    if outcome == "available":
        call.set_task(
            "outreach",
            objective=(
                f"You are calling {alumni_name}, a Westfield University alumnus "
                f"who graduated in {graduation_year} from {major}. Reconnect "
                f"warmly and invite them to make a gift. Be conversational, "
                f"grateful, and never pushy."
            ),
            checklist=[
                guava.Say(
                    f"I hope you're doing well! I'm reaching out to reconnect "
                    f"with fellow alumni — class of {graduation_year} from "
                    f"{major} — and share some exciting things happening on "
                    f"campus. Do you have just a few minutes to chat?"
                ),
                guava.Field(
                    key="pledge_response",
                    description="The alumnus's response to the giving invitation",
                    field_type="multiple_choice",
                    choices=["pledges amount", "not now", "not interested"],
                    required=True,
                ),
            ],
        )
    elif outcome == "do_not_contact":
        logging.info("Alumnus %s requested no further contact.", alumni_name)
        call.hangup(
            final_instructions=(
                "Acknowledge their request politely. Let them know they have been "
                "removed from our outreach list and will not be contacted again, and politely say goodbye."
            )
        )
    elif outcome == "wrong_number":
        logging.info("Wrong number reached for %s.", alumni_name)
        call.hangup(final_instructions="Apologize for the mistake and wish them well, and politely say goodbye.")
    else:
        logging.info("Could not reach %s (outcome: %s).", alumni_name, outcome)
        call.hangup()


@agent.on_task_complete("outreach")
def on_outreach_done(call: guava.Call) -> None:
    alumni_name = call.get_variable("name")
    pledge_response = call.get_field("pledge_response")

    if pledge_response == "pledges amount":
        call.set_task(
            "collect_pledge",
            objective=(
                f"{alumni_name} is open to making a gift. Collect the pledge "
                f"details — amount, gift type, designation preference, and "
                f"target date. Be grateful and warm."
            ),
            checklist=[
                guava.Field(
                    key="gift_amount",
                    description="The dollar amount the alumnus would like to give or pledge",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="gift_type",
                    description="The type of gift the alumnus prefers",
                    field_type="multiple_choice",
                    choices=["one_time", "monthly", "annual"],
                    required=True,
                ),
                guava.Field(
                    key="designation_preference",
                    description=(
                        "Where the alumnus would like their gift directed, such as "
                        "scholarship, athletics, general fund, or another area"
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="pledge_date",
                    description="The date by which the alumnus intends to fulfill their pledge",
                    field_type="text",
                    required=False,
                ),
            ],
        )
    elif pledge_response == "not now":
        call.set_task(
            "schedule_callback",
            objective=(
                f"{alumni_name} is not ready to make a gift right now but may be "
                f"open to it later. Ask if there is a better time to reconnect and "
                f"schedule a callback. Be understanding and thankful for their time."
            ),
            checklist=[
                guava.Field(
                    key="callback_timeframe",
                    description="When the alumnus would prefer to be contacted again",
                    field_type="text",
                    required=True,
                ),
            ],
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {alumni_name} warmly for their time. Respect their "
                f"decision completely — do not push or try to change their mind. "
                f"Let them know they are always welcome in the Westfield alumni "
                f"community and wish them well, and politely say goodbye."
            )
        )


@agent.on_task_complete("collect_pledge")
def on_pledge_collected(call: guava.Call) -> None:
    alumni_name = call.get_variable("name")
    call.hangup(
        final_instructions=(
            f"Thank {alumni_name} sincerely for their generous pledge to "
            f"Westfield University. Let them know they will receive a follow-up "
            f"email with details on how to complete their gift. Wish them a "
            f"wonderful day, and politely say goodbye."
        )
    )


@agent.on_task_complete("schedule_callback")
def on_callback_scheduled(call: guava.Call) -> None:
    alumni_name = call.get_variable("name")
    call.hangup(
        final_instructions=(
            f"Thank {alumni_name} for their time and let them know we'll reach "
            f"out again at the time they suggested. Invite them to stay connected "
            f"with the alumni community in the meantime, and wish them well, and politely say goodbye."
        )
    )


@agent.on_action_request
def on_action_request(call: guava.Call, intent_summary: str):
    return _mid_call_intent.classify(intent_summary)


@agent.on_action("do_not_contact")
def handle_dnc(call: guava.Call) -> None:
    logging.info("Alumnus %s requested DNC mid-call.", call.get_variable("name"))
    call.hangup(
        final_instructions=(
            "Acknowledge their request. Let them know they've been removed from the "
            "contact list and won't be called again. Thank them and wish them well, and politely say goodbye."
        )
    )


@agent.on_action("speak_to_someone")
def handle_speak_to_someone(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            "Let them know that someone from Westfield University Alumni Relations "
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
        "alumni_name": call.get_variable("name"),
        "graduation_year": call.get_variable("graduation_year"),
        "major": call.get_variable("major"),
        "pledge_response": call.get_field("pledge_response"),
        "gift_amount": call.get_field("gift_amount"),
        "gift_type": call.get_field("gift_type"),
        "designation_preference": call.get_field("designation_preference"),
        "pledge_date": call.get_field("pledge_date"),
        "callback_timeframe": call.get_field("callback_timeframe"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Alumni fundraising call to collect gift pledges and preferences"
    )
    parser.add_argument("phone", help="Phone number to call (e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Full name of the alumnus")
    parser.add_argument(
        "--graduation-year",
        required=True,
        help="Year the alumnus graduated (e.g. '2015')",
    )
    parser.add_argument(
        "--major",
        default="your program",
        help="Alumnus's field of study (default: 'your program')",
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
            "name": args.name,
            "graduation_year": args.graduation_year,
            "major": args.major,
        },
    )

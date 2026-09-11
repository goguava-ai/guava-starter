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
    name="Drew",
    organization="Keystone Property & Casualty — Risk Assessment",
    purpose=(
        "schedule a property inspection appointment and collect pre-inspection "
        "risk information to help the inspector prepare for their visit"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
    "speak_to_someone": "The caller wants to speak to a real person, an agent, or the risk assessment team",
})


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(
        contact_full_name=call.get_variable("contact_name"),
        voicemail_message=(
            f"Hi, this is Drew from the Risk Assessment team at Keystone Property "
            f"& Casualty calling for {call.get_variable('contact_name')}. We're "
            f"reaching out to schedule a routine property inspection. Please call "
            f"us back at 1-800-555-0100 at your convenience. Thank you."
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    contact_name = call.get_variable("contact_name")
    policy_number = call.get_variable("policy_number")

    if outcome == "available":
        call.set_task(
            "risk_survey",
            objective=(
                f"Call {contact_name} regarding policy {policy_number} to coordinate "
                f"a property inspection and gather pre-inspection risk data. Be "
                f"friendly and explain that the inspection is a standard part of the "
                f"policy process."
            ),
            checklist=[
                guava.Say(
                    f"I'm calling about your policy {policy_number}. We'd like to "
                    f"schedule a routine property inspection and I have a few quick "
                    f"questions to help our inspector prepare."
                ),
                guava.Field(
                    key="inspection_date_preference",
                    description="The insured's preferred date or date range for the inspection",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="access_instructions",
                    description=(
                        "Any special instructions for accessing the property, such "
                        "as gate codes, key lockbox location, or contact person on site"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="dogs_on_property",
                    description=(
                        "Whether there are dogs or other animals on the property that "
                        "the inspector should be aware of"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="renovation_in_progress",
                    description=(
                        "Whether any active renovations or construction work are "
                        "currently underway at the property"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="electrical_panel_age",
                    description=(
                        "The approximate age or last replacement year of the main "
                        "electrical panel, if known"
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="hvac_age",
                    description=(
                        "The approximate age or last replacement year of the primary "
                        "HVAC system, if known"
                    ),
                    field_type="text",
                    required=False,
                ),
            ],
        )
    elif outcome == "do_not_contact":
        logging.info("Insured %s requested no further contact.", contact_name)
        call.hangup(
            final_instructions=(
                "Acknowledge their request. Let them know they will not be contacted "
                "again by phone and that inspection scheduling information will be "
                "sent by mail, and politely say goodbye."
            )
        )
    elif outcome == "wrong_number":
        logging.info("Wrong number for %s.", contact_name)
        call.hangup(final_instructions="Apologize for the mistake and wish them well, and politely say goodbye.")
    else:
        logging.info("Could not reach %s (outcome: %s).", contact_name, outcome)
        call.hangup()


@agent.on_task_complete("risk_survey")
def on_survey_done(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    dogs = call.get_field("dogs_on_property")
    renovation = call.get_field("renovation_in_progress")

    has_risk_factors = (
        (dogs and dogs.lower() not in ("no", "none", "n/a"))
        or (renovation and renovation.lower() not in ("no", "none", "n/a"))
    )

    if has_risk_factors:
        call.set_task(
            "risk_followup",
            objective=(
                f"{contact_name} reported risk factors that require additional "
                f"clarification. Ask follow-up questions about the specific risks "
                f"to ensure the inspector is properly prepared and safety measures "
                f"are documented."
            ),
            checklist=[
                guava.Field(
                    key="risk_mitigation",
                    description=(
                        "What safety measures are in place for the identified risks "
                        "(e.g., dog will be contained during inspection, renovation "
                        "areas will be cordoned off)"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="inspector_special_notes",
                    description=(
                        "Any other details the inspector should know before arriving"
                    ),
                    field_type="text",
                    required=False,
                ),
            ],
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {contact_name} for their time. Let them know the inspection "
                f"appointment will be confirmed by email and they will receive a "
                f"reminder the day before. The inspection typically takes 30 to 45 "
                f"minutes, and wish them a great day, and politely say goodbye."
            )
        )


@agent.on_task_complete("risk_followup")
def on_risk_followup_done(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    call.hangup(
        final_instructions=(
            f"Thank {contact_name} for providing that additional information. "
            f"Let them know the inspection will be confirmed by email and the "
            f"inspector will be briefed on the details they shared. Wish them "
            f"a great day, and politely say goodbye."
        )
    )


@agent.on_action_request
def on_action_request(call: guava.Call, intent_summary: str):
    return _mid_call_intent.classify(intent_summary)


@agent.on_action("do_not_contact")
def handle_dnc(call: guava.Call) -> None:
    logging.info("Insured %s requested DNC mid-call.", call.get_variable("contact_name"))
    call.hangup(
        final_instructions=(
            "Acknowledge their request. Let them know they have been removed from "
            "the contact list and will not be called again, and wish them well, "
            "and politely say goodbye."
        )
    )


@agent.on_action("speak_to_someone")
def handle_speak_to_someone(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            "Let them know someone from the Risk Assessment team will call them "
            "back within one business day. Ask if there's a preferred time and "
            "thank them, and politely say goodbye."
        )
    )


@agent.on_outbound_failed
def on_outbound_failed(event: OutboundCallFailed) -> None:
    logging.error("Outbound call failed: %s (code %d)", event.error_reason, event.error_code)


@agent.on_session_end
def on_session_end(call: guava.Call, event: BotSessionEnded) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "use_case": "risk_survey",
        "contact_name": call.get_variable("contact_name"),
        "policy_number": call.get_variable("policy_number"),
        "inspection_date_preference": call.get_field("inspection_date_preference"),
        "access_instructions": call.get_field("access_instructions"),
        "dogs_on_property": call.get_field("dogs_on_property"),
        "renovation_in_progress": call.get_field("renovation_in_progress"),
        "electrical_panel_age": call.get_field("electrical_panel_age"),
        "hvac_age": call.get_field("hvac_age"),
        "risk_mitigation": call.get_field("risk_mitigation"),
        "inspector_special_notes": call.get_field("inspector_special_notes"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound risk survey and inspection scheduling for Keystone Property & Casualty"
    )
    parser.add_argument("phone", help="Phone number to dial")
    parser.add_argument("--name", required=True, help="Full name of the insured")
    parser.add_argument("--policy-number", required=True, help="Policy number")
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
            "policy_number": args.policy_number,
        },
    )

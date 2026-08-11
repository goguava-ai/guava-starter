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
    name="Reese",
    organization="Springfield County Public Health Department",
    purpose=(
        "conduct a brief anonymous public health survey to gather "
        "epidemiological data and offer resource information when "
        "concerning health indicators are reported"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
})


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(
        contact_full_name=call.get_variable("respondent_name"),
        voicemail_message=(
            f"Hi, this is Reese from the Springfield County Public Health "
            f"Department calling for {call.get_variable('respondent_name')}. "
            f"We are conducting a brief, voluntary community health survey. "
            f"Please call us back at your convenience if you would like to "
            f"participate. Thank you."
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    respondent_name = call.get_variable("respondent_name")

    if outcome == "available":
        call.set_task(
            "survey",
            objective=(
                f"Conduct a short, voluntary, and anonymous public health survey "
                f"with {respondent_name}. The purpose is to gather epidemiological "
                f"data to help the county understand community health status and "
                f"improve public health programs. Assure the respondent that no "
                f"personally identifying information will be recorded and "
                f"participation is entirely voluntary. Be respectful, neutral, "
                f"and brief."
            ),
            checklist=[
                guava.Say(
                    "We are conducting a brief, voluntary, and anonymous community "
                    "health survey. Your responses help us understand the health "
                    "needs of our community. This takes approximately two to three "
                    "minutes. No personally identifying information will be recorded. "
                    "Would you be willing to participate?"
                ),
                guava.Field(
                    key="household_count",
                    description="How many people, including the respondent, currently live in their household",
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="vaccinations_up_to_date",
                    description=(
                        "Whether the respondent believes the vaccinations for people "
                        "in their household are generally up to date, including "
                        "routine immunizations"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="flu_shot_this_season",
                    description=(
                        "Whether anyone in the household has received a flu shot "
                        "during the current flu season"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="chronic_conditions_present",
                    description=(
                        "In general terms, whether anyone in the household manages "
                        "a chronic health condition such as diabetes, heart disease, "
                        "asthma, or a similar ongoing condition — no specific "
                        "diagnoses are required"
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="healthcare_access_barriers",
                    description=(
                        "Whether anyone in the household has experienced difficulty "
                        "accessing healthcare in the past year, such as cost, "
                        "transportation, wait times, or availability of providers"
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="health_insurance_status",
                    description=(
                        "Whether all members of the household currently have health "
                        "insurance coverage of some kind"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="primary_care_physician_assigned",
                    description=(
                        "Whether the household members have an assigned primary care "
                        "physician or regular healthcare provider for routine care"
                    ),
                    field_type="text",
                    required=True,
                ),
            ],
        )
    elif outcome == "do_not_contact":
        logging.info("Respondent %s requested no further contact.", respondent_name)
        call.hangup(
            final_instructions=(
                "Acknowledge their request. Let them know they will not be "
                "contacted again. Thank them and wish them well, and politely say goodbye."
            )
        )
    elif outcome == "wrong_number":
        logging.info("Wrong number reached for %s.", respondent_name)
        call.hangup(final_instructions="Apologize for the mistake and wish them well, and politely say goodbye.")
    else:
        logging.info("Could not reach %s (outcome: %s).", respondent_name, outcome)
        call.hangup()


@agent.on_task_complete("survey")
def on_survey_done(call: guava.Call) -> None:
    respondent_name = call.get_variable("respondent_name")
    insurance = call.get_field("health_insurance_status")
    access_barriers = call.get_field("healthcare_access_barriers")

    # If concerning indicators: no insurance or significant access barriers
    has_concerns = False
    if insurance and any(word in insurance.lower() for word in ["no", "not", "none", "uninsured"]):
        has_concerns = True
    if access_barriers and any(word in access_barriers.lower() for word in ["yes", "difficulty", "hard", "unable", "cost"]):
        has_concerns = True

    if has_concerns:
        call.set_task(
            "resource_info",
            objective=(
                f"{respondent_name} reported potential healthcare access concerns "
                f"during the survey. Offer to provide information about local public "
                f"health resources, free or low-cost clinics, and insurance enrollment "
                f"assistance available through the county. Be helpful but not pushy — "
                f"this is optional."
            ),
            checklist=[
                guava.Field(
                    key="wants_resource_info",
                    description=(
                        "Ask whether the respondent would like information about "
                        "free or low-cost healthcare resources available in "
                        "Springfield County"
                    ),
                    field_type="multiple_choice",
                    choices=["yes", "no"],
                    required=True,
                ),
            ],
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {respondent_name} sincerely for participating in the survey. "
                f"Let them know their responses contribute to improving public health "
                f"services in Springfield County. Remind them that all responses are "
                f"anonymous. If they have questions about local public health resources, "
                f"encourage them to reach out to the Springfield County Public Health "
                f"Department, and wish them well, and politely say goodbye."
            )
        )


@agent.on_task_complete("resource_info")
def on_resource_done(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            f"Thank {call.get_variable('respondent_name')} sincerely for their "
            f"participation. If they requested resource information, let them know "
            f"the Springfield County Public Health Department offers free health "
            f"screenings, vaccination clinics, and can help with insurance enrollment. "
            f"Let them know they can reach out to the department for more details. Remind them all "
            f"survey responses are anonymous, and wish them well, and politely say goodbye."
        )
    )


@agent.on_action_request
def on_action_request(call: guava.Call, intent_summary: str):
    return _mid_call_intent.classify(intent_summary)


@agent.on_action("do_not_contact")
def handle_dnc(call: guava.Call) -> None:
    logging.info("Respondent %s requested DNC mid-call.", call.get_variable("respondent_name"))
    call.hangup(
        final_instructions=(
            "Acknowledge their request. Let them know they will not be contacted "
            "again. Thank them and wish them well, and politely say goodbye."
        )
    )


@agent.on_outbound_failed
def on_outbound_failed(event: OutboundCallFailed) -> None:
    logging.error("Outbound call failed: %s (code %d)", event.error_reason, event.error_code)


@agent.on_session_end
def on_session_end(call: guava.Call, event: BotSessionEnded) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "use_case": "public_health_survey",
        "respondent_name": call.get_variable("respondent_name"),
        "household_count": call.get_field("household_count"),
        "vaccinations_up_to_date": call.get_field("vaccinations_up_to_date"),
        "flu_shot_this_season": call.get_field("flu_shot_this_season"),
        "chronic_conditions_present": call.get_field("chronic_conditions_present"),
        "healthcare_access_barriers": call.get_field("healthcare_access_barriers"),
        "health_insurance_status": call.get_field("health_insurance_status"),
        "primary_care_physician_assigned": call.get_field("primary_care_physician_assigned"),
        "wants_resource_info": call.get_field("wants_resource_info"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound public health survey call for Springfield County Public Health Department."
    )
    parser.add_argument("phone", help="Resident phone number to call (E.164 format).")
    parser.add_argument("--name", required=True, help="Full name of the respondent.")
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
            "respondent_name": args.name,
        },
    )

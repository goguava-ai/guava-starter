# SDK conformance: guava-sdk 0.35.0 (2026-07-21)
import argparse
import json
import logging
import os
from datetime import datetime, timezone

import guava
from guava import logging_utils
from guava.helpers.llm import IntentRecognizer

agent = guava.Agent(
    name="Emery",
    organization="Acme Realty Group",
    purpose=(
        "gather post-closing feedback from buyers and sellers, probe on low "
        "satisfaction scores to understand pain points, and invite satisfied "
        "clients to the referral program"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
    "speak_to_agent": "The caller wants to speak to their agent or someone at the office",
})


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(
        contact_full_name=call.get_variable("contact_name"),
        voicemail_message=(
            f"Hi, this is Emery from Acme Realty Group calling for "
            f"{call.get_variable('contact_name')}. Congratulations on your recent "
            f"closing at {call.get_variable('property_address')}! We'd love to "
            f"hear about your experience — it will only take a few minutes. "
            f"Please call us back at your convenience. Thank you!"
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    contact_name = call.get_variable("contact_name")
    agent_name = call.get_variable("agent_name")
    property_address = call.get_variable("property_address")

    if outcome == "available":
        call.set_task(
            "post_close_survey",
            objective=(
                f"Call {contact_name} to congratulate them on the recent closing "
                f"of {property_address} and gather feedback about their experience "
                f"with {agent_name} at Acme Realty Group. Be warm and "
                f"celebratory. This is a celebration call, not a cold survey."
            ),
            checklist=[
                guava.Say(
                    f"Congratulations on your recent closing at {property_address}! "
                    f"I'm reaching out to hear about your experience with "
                    f"{agent_name}. Your feedback means a great deal to our team."
                ),
                guava.Field(
                    key="overall_rating",
                    description=(
                        "Overall satisfaction rating on a scale of 1 to 5, where "
                        "1 is very unsatisfied and 5 is very satisfied"
                    ),
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="agent_communication_rating",
                    description=(
                        f"Rating of {agent_name}'s communication on a scale of 1 to 5 "
                        f"— responsiveness, keeping them informed, and explaining steps"
                    ),
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="would_recommend",
                    description=(
                        "Whether the client would recommend Acme Realty Group "
                        "to friends, family, or colleagues"
                    ),
                    field_type="multiple_choice",
                    choices=["yes", "no", "maybe"],
                    required=True,
                ),
                guava.Field(
                    key="most_helpful_aspect",
                    description=(
                        f"The most helpful or memorable part of working with "
                        f"{agent_name} or the Pinnacle team"
                    ),
                    field_type="text",
                    required=False,
                ),
            ],
        )
    elif outcome == "do_not_contact":
        logging.info("Client %s requested no further contact.", contact_name)
        call.hangup(
            final_instructions=(
                "Acknowledge their request. Let them know they will not be contacted "
                "again. Congratulate them on their closing and wish them well, and politely say goodbye."
            )
        )
    elif outcome == "wrong_number":
        logging.info("Wrong number reached for %s.", contact_name)
        call.hangup(final_instructions="Apologize for the mistake and wish them well, and politely say goodbye.")
    else:
        logging.info("Could not reach %s (outcome: %s).", contact_name, outcome)
        call.hangup()


@agent.on_task_complete("post_close_survey")
def on_survey_done(call: guava.Call) -> None:
    overall = call.get_field("overall_rating")
    contact_name = call.get_variable("contact_name")

    if overall is not None and overall <= 2:
        call.set_task(
            "low_satisfaction_probe",
            objective=(
                f"{contact_name} gave a low overall rating ({overall}/5). "
                f"Ask what specifically went wrong during the process — was it "
                f"communication, timeline, pricing, paperwork, or something else? "
                f"Be empathetic and listen carefully. Let them know their feedback "
                f"will be shared with leadership."
            ),
            checklist=[
                guava.Field(
                    key="pain_points",
                    description=(
                        "What specifically the client was unhappy about during "
                        "the buying or selling process"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="areas_for_improvement",
                    description=(
                        "What Pinnacle could have done differently to improve "
                        "the experience"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="wants_followup",
                    description=(
                        "Whether the client would like a follow-up call from "
                        "the office manager to discuss their concerns"
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
                f"Thank {contact_name} sincerely for their feedback. Let them know "
                f"it will be shared directly with {call.get_variable('agent_name')} "
                f"and the Pinnacle leadership team. Mention the referral program — "
                f"Pinnacle rewards clients who connect them with new buyers or "
                f"sellers. Congratulate them once more and wish them all the best, and politely say goodbye."
            )
        )


@agent.on_task_complete("low_satisfaction_probe")
def on_low_satisfaction_done(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    wants_followup = call.get_field("wants_followup")

    if wants_followup == "yes":
        call.hangup(
            final_instructions=(
                f"Thank {contact_name} for sharing that feedback — it genuinely "
                f"helps Pinnacle improve. Confirm that the office manager will "
                f"reach out within two business days to discuss their concerns "
                f"personally, and wish them well, and politely say goodbye."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {contact_name} for their honesty. Assure them their "
                f"feedback will be reviewed by leadership. Wish them all the best "
                f"in their new home or next chapter, and politely say goodbye."
            )
        )


@agent.on_action_request
def on_action_request(call: guava.Call, intent_summary: str):
    return _mid_call_intent.classify(intent_summary)


@agent.on_action("do_not_contact")
def handle_dnc(call: guava.Call) -> None:
    logging.info("Client %s requested DNC mid-call.", call.get_variable("contact_name"))
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
            f"Let them know that {call.get_variable('agent_name')} or someone "
            f"from the Pinnacle office will call them back within one business "
            f"day. Ask if there is a preferred time and thank them, and politely say goodbye."
        )
    )


@agent.on_outbound_failed
def on_outbound_failed(event: guava.OutboundCallFailed) -> None:
    logging.error("Outbound call failed: %s (code %d)", event.error_reason, event.error_code)


@agent.on_session_end
def on_session_end(call: guava.Call, event: guava.BotSessionEnded) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "contact_name": call.get_variable("contact_name"),
        "agent_name": call.get_variable("agent_name"),
        "property_address": call.get_variable("property_address"),
        "overall_rating": call.get_field("overall_rating"),
        "agent_communication_rating": call.get_field("agent_communication_rating"),
        "would_recommend": call.get_field("would_recommend"),
        "most_helpful_aspect": call.get_field("most_helpful_aspect"),
        "pain_points": call.get_field("pain_points"),
        "areas_for_improvement": call.get_field("areas_for_improvement"),
        "wants_followup": call.get_field("wants_followup"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound post-close survey call for Acme Realty Group"
    )
    parser.add_argument("phone", help="The client's phone number to call")
    parser.add_argument("--name", required=True, help="Full name of the client to reach")
    parser.add_argument(
        "--agent-name",
        required=True,
        help="Full name of the agent who handled the transaction",
    )
    parser.add_argument(
        "--property-address",
        required=True,
        help="Address of the property that was bought or sold",
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
            "agent_name": args.agent_name,
            "property_address": args.property_address,
        },
    )

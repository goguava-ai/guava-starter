import argparse
import json
import logging
import os
from datetime import datetime, timezone

import guava
from guava import logging_utils

agent = guava.Agent(
    name="Morgan",
    organization="Pinnacle Realty Group",
    purpose=(
        "gather post-closing feedback from buyers and sellers to help "
        "Pinnacle Realty Group improve agent performance and invite satisfied "
        "clients to join the referral program"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(contact_full_name=call.get_variable("contact_name"))


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    contact_name = call.get_variable("contact_name")
    agent_name = call.get_variable("agent_name")
    property_address = call.get_variable("property_address")

    if outcome == "unavailable":
        logging.warning(
            "Could not reach %s for post-close survey (agent: %s, property: %s).",
            contact_name,
            agent_name,
            property_address,
        )
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "vertical": "real_estate",
            "use_case": "post_close_survey",
            "contact_name": contact_name,
            "agent_name": agent_name,
            "property_address": property_address,
            "status": "recipient_unavailable",
        }
        print(json.dumps(results, indent=2))
        call.hangup(
            final_instructions=(
                f"Leave a brief, warm voicemail for {contact_name}. "
                "Introduce yourself as Morgan from Pinnacle Realty Group and congratulate "
                f"them on their recent closing at {property_address}. "
                "Let them know you're calling to gather a few minutes of feedback about "
                f"their experience with {agent_name} and to share information about "
                "a client referral program. Ask them to call back when convenient. "
                "Keep it upbeat and under 30 seconds."
            )
        )
    elif outcome == "available":
        call.set_task(
            "post_close_survey",
            objective=(
                f"You are calling {contact_name} to congratulate them on the recent "
                f"closing of {property_address} and gather their feedback about their "
                f"experience working with {agent_name} at Pinnacle Realty Group. "
                "Be warm, celebratory, and genuinely curious. Let them know their feedback "
                "directly shapes how agents are recognized and how the company improves. "
                "Keep the tone conversational — this is a celebration call, not a cold survey."
            ),
            checklist=[
                guava.Say(
                    f"Congratulations again on your recent closing at {property_address}! "
                    f"On behalf of everyone at Pinnacle Realty Group, we're so excited for you. "
                    f"I'm Morgan, and I'm reaching out to hear about your experience with "
                    f"{agent_name}. Your feedback means a great deal to our team and "
                    f"only takes a few minutes."
                ),
                guava.Field(
                    key="overall_experience_rating",
                    description=(
                        "On a scale of 1 to 5, with 5 being excellent and 1 being poor, "
                        "how would you rate your overall experience with Pinnacle Realty Group "
                        "from start to close?"
                    ),
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="agent_communication_rating",
                    description=(
                        f"Still using a scale of 1 to 5, how would you rate {agent_name}'s "
                        "communication throughout the process — things like responsiveness, "
                        "keeping you informed, and explaining each step clearly?"
                    ),
                    field_type="integer",
                    required=True,
                ),
                guava.Field(
                    key="would_recommend",
                    description=(
                        "Would you recommend Pinnacle Realty Group to a friend, family member, "
                        "or colleague who is buying or selling a home?"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="most_helpful_aspect",
                    description=(
                        "What was the most helpful or memorable part of working with "
                        f"{agent_name} or our team during this transaction?"
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="areas_for_improvement",
                    description=(
                        "Is there anything we could have done better or differently "
                        "to make your experience even smoother?"
                    ),
                    field_type="text",
                    required=False,
                ),
                guava.Field(
                    key="open_to_referral_program",
                    description=(
                        "We have a referral program that rewards clients who connect us with "
                        "new buyers or sellers. Would you be interested in learning more about it?"
                    ),
                    field_type="text",
                    required=True,
                ),
            ],
        )


@agent.on_task_complete("post_close_survey")
def on_done(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    agent_name = call.get_variable("agent_name")
    property_address = call.get_variable("property_address")
    overall = call.get_field("overall_experience_rating")
    communication = call.get_field("agent_communication_rating")
    referral_interest = (call.get_field("open_to_referral_program") or "").lower()

    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "vertical": "real_estate",
        "use_case": "post_close_survey",
        "contact_name": contact_name,
        "agent_name": agent_name,
        "property_address": property_address,
        "fields": {
            "overall_experience_rating": overall,
            "agent_communication_rating": communication,
            "would_recommend": call.get_field("would_recommend"),
            "most_helpful_aspect": call.get_field("most_helpful_aspect"),
            "areas_for_improvement": call.get_field("areas_for_improvement"),
            "open_to_referral_program": call.get_field("open_to_referral_program"),
        },
    }
    print(json.dumps(results, indent=2))
    logging.info("Post-close survey results captured: %s", results)

    referral_note = (
        "Also mention that someone from our team will be in touch shortly with "
        "details about the referral program and how they can earn rewards for "
        "connecting us with new clients. "
        if any(word in referral_interest for word in ["yes", "sure", "interested", "open"])
        else ""
    )

    call.hangup(
        final_instructions=(
            f"Thank {contact_name} sincerely for taking the time to share their "
            f"feedback — let them know it will be shared directly with {agent_name} "
            "and the Pinnacle leadership team. "
            + referral_note +
            "Congratulate them once more on their closing, wish them all the best in "
            "their new home or next chapter, and close the call warmly and genuinely."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Post-close satisfaction survey outbound call."
    )
    parser.add_argument("phone", help="The client's phone number to call.")
    parser.add_argument("--name", required=True, help="Full name of the client to reach.")
    parser.add_argument(
        "--agent-name",
        required=True,
        help="Full name of the agent who handled the transaction.",
    )
    parser.add_argument(
        "--property-address",
        required=True,
        help="Address of the property that was bought or sold.",
    )
    args = parser.parse_args()

    logging.info(
        "Initiating post-close survey call to %s (%s) for property %s (agent: %s).",
        args.name,
        args.phone,
        args.property_address,
        args.agent_name,
    )

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "contact_name": args.name,
            "agent_name": args.agent_name,
            "property_address": args.property_address,
        },
    )

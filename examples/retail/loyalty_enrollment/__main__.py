# SDK conformance: guava-sdk 0.39.0 (2026-08-26)
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
    organization="ShopNow",
    purpose=(
        "welcome first-time buyers to ShopNow, introduce the loyalty rewards "
        "program, and enroll interested customers or schedule a follow-up"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
    "speak_to_someone": "The caller wants to speak to a real person or customer service representative",
})


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(
        contact_full_name=call.get_variable("customer_name"),
        voicemail_message=(
            f"Hi, this is Lane from ShopNow calling for "
            f"{call.get_variable('customer_name')}. We wanted to welcome you as a "
            f"new customer and share some exciting rewards you've unlocked. "
            f"No action needed — feel free to call us back anytime. Thank you!"
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    customer_name = call.get_variable("customer_name")
    order_number = call.get_variable("order_number")

    if outcome == "available":
        call.set_task(
            "enrollment",
            objective=(
                f"Welcome {customer_name} as a new ShopNow customer following order "
                f"#{order_number}. Introduce the ShopNow Rewards loyalty program — "
                f"points on every purchase, exclusive member discounts, birthday rewards, "
                f"and early access to sales. Enrollment is free. Determine their interest "
                f"level and proceed accordingly."
            ),
            checklist=[
                guava.Say(
                    f"Welcome — we're thrilled to have you as a new customer! Your "
                    f"order #{order_number} is on its way, and I wanted to personally "
                    f"tell you about our ShopNow Rewards program. As a member, you "
                    f"earn points on every purchase, get exclusive discounts, a special "
                    f"birthday reward, and early access to our biggest sales. Best of "
                    f"all, it's completely free."
                ),
                guava.Field(
                    key="interest_level",
                    description=(
                        "The customer's interest in the loyalty program: enroll, not now, "
                        "or not interested"
                    ),
                    field_type="multiple_choice",
                    choices=["enroll", "not_now", "not_interested"],
                    required=True,
                ),
            ],
        )
    elif outcome == "do_not_contact":
        logging.info("Customer %s requested no further contact.", customer_name)
        call.hangup(
            final_instructions=(
                "Acknowledge their request politely. Let them know they have been "
                "removed from our outreach list and will not be contacted again, and politely say goodbye."
            )
        )
    elif outcome == "wrong_number":
        logging.info("Wrong number reached for %s.", customer_name)
        call.hangup(final_instructions="Apologize for the mistake and wish them well, and politely say goodbye.")
    else:
        logging.info("Could not reach %s (outcome: %s).", customer_name, outcome)
        call.hangup()


@agent.on_task_complete("enrollment")
def on_enrollment_done(call: guava.Call) -> None:
    interest = call.get_field("interest_level")
    customer_name = call.get_variable("customer_name")

    if interest == "enroll":
        call.set_task(
            "collect_enrollment_details",
            objective=(
                f"{customer_name} wants to enroll in ShopNow Rewards. Collect their "
                f"email address for rewards notifications and explain the benefits "
                f"they'll start receiving immediately."
            ),
            checklist=[
                guava.Field(
                    key="email_address",
                    description="The customer's email address for rewards notifications",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="preferred_channel",
                    description="Preferred channel for rewards updates",
                    field_type="multiple_choice",
                    choices=["email", "sms", "both"],
                    required=True,
                ),
                guava.Field(
                    key="birthday_month",
                    description=(
                        "The customer's birthday month and day for their annual birthday "
                        "reward. Leave blank if they prefer not to share."
                    ),
                    field_type="text",
                    required=False,
                ),
            ],
        )
    elif interest == "not_now":
        call.set_task(
            "soft_followup",
            objective=(
                f"{customer_name} is not ready to enroll right now. Offer to send "
                f"them information about the program so they can review it later, "
                f"or ask if they'd prefer a callback at a better time."
            ),
            checklist=[
                guava.Field(
                    key="followup_preference",
                    description="Whether the customer wants info sent or a callback scheduled",
                    field_type="multiple_choice",
                    choices=["send_info", "schedule_callback", "no_thanks"],
                    required=True,
                ),
                guava.Field(
                    key="callback_time",
                    description=(
                        "If the customer wants a callback, when they'd prefer to be reached. "
                        "Leave blank if they chose another option."
                    ),
                    field_type="text",
                    required=False,
                ),
            ],
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {customer_name} for their time. Let them know the program "
                f"is always available if they change their mind, and wish them a great day, and politely say goodbye."
            )
        )


@agent.on_task_complete("collect_enrollment_details")
def on_enrollment_details_done(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    call.hangup(
        final_instructions=(
            f"Congratulate {customer_name} on joining ShopNow Rewards. Let them know "
            f"a welcome email will be sent to the address they provided. Remind them "
            f"they start earning points on their very next purchase. Wish them a "
            f"wonderful day, and politely say goodbye."
        )
    )


@agent.on_task_complete("soft_followup")
def on_soft_followup_done(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    call.hangup(
        final_instructions=(
            f"Thank {customer_name} for their time. If they requested info, confirm "
            f"it will be sent. If they scheduled a callback, confirm the time. "
            f"Wish them a great day, and politely say goodbye."
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
            "Let them know that a ShopNow team member will call them back within "
            "one business day. Ask if there's a preferred time and thank them, and politely say goodbye."
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
        "order_number": call.get_variable("order_number"),
        "interest_level": call.get_field("interest_level"),
        "email_address": call.get_field("email_address"),
        "preferred_channel": call.get_field("preferred_channel"),
        "birthday_month": call.get_field("birthday_month"),
        "followup_preference": call.get_field("followup_preference"),
        "callback_time": call.get_field("callback_time"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound loyalty enrollment call for ShopNow"
    )
    parser.add_argument("phone", help="Customer phone number to call")
    parser.add_argument("--name", required=True, help="Customer full name")
    parser.add_argument("--order-number", required=True, help="Customer's first order number")
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
            "order_number": args.order_number,
        },
    )

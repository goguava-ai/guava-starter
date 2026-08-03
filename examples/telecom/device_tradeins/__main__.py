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
    name="Wren",
    organization="Nexus Mobile",
    purpose=(
        "reach out to customers eligible for a device upgrade, assess their "
        "current device condition, quote a trade-in value, and help them "
        "choose a trade-in method"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
    "speak_to_someone": "The caller wants to speak to a real person or sales representative",
})


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(
        contact_full_name=call.get_variable("customer_name"),
        voicemail_message=(
            f"Hi, this is Wren from Nexus Mobile calling for "
            f"{call.get_variable('customer_name')}. Great news — your device "
            f"qualifies for our trade-in upgrade program. No action needed right "
            f"now — call us back at your convenience to learn more. Thank you!"
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    customer_name = call.get_variable("customer_name")
    current_device = call.get_variable("current_device")
    account_number = call.get_variable("account_number")

    if outcome == "available":
        call.set_task(
            "assess_device",
            objective=(
                f"Speak with {customer_name} (account #{account_number}) about "
                f"trading in their {current_device}. Assess the device condition."
            ),
            checklist=[
                guava.Say(
                    f"I have some great news — your {current_device} qualifies "
                    f"for our device upgrade program. I'd love to walk you "
                    f"through your options."
                ),
                guava.Field(
                    key="device_condition",
                    description=(
                        "The condition of the customer's current device: excellent "
                        "(like new, no scratches), good (minor wear, fully functional), "
                        "fair (visible wear, some issues), or poor (significant damage)"
                    ),
                    field_type="multiple_choice",
                    choices=["excellent", "good", "fair", "poor"],
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


@agent.on_task_complete("assess_device")
def on_device_assessed(call: guava.Call) -> None:
    condition = call.get_field("device_condition")
    customer_name = call.get_variable("customer_name")
    current_device = call.get_variable("current_device")

    if condition in ("excellent", "good"):
        trade_value = "$250" if condition == "excellent" else "$175"
        call.set_task(
            "present_trade_offer",
            objective=(
                f"{customer_name}'s {current_device} is in {condition} condition. "
                f"Quote a trade-in value of {trade_value}. Explain they can apply "
                f"this toward any new device. Ask if they're interested and which "
                f"trade-in method they prefer."
            ),
            checklist=[
                guava.Say(
                    f"Great news — based on the {condition} condition of your "
                    f"{current_device}, we can offer you {trade_value} in trade-in "
                    f"value toward a brand new device."
                ),
                guava.Field(
                    key="interested",
                    description="Whether the customer is interested in the trade-in offer",
                    field_type="multiple_choice",
                    choices=["yes", "no", "thinking_about_it"],
                    required=True,
                ),
                guava.Field(
                    key="trade_method",
                    description=(
                        "The customer's preferred trade-in method: visit a Nexus Mobile "
                        "store or use the mail-in program with a prepaid shipping kit"
                    ),
                    field_type="multiple_choice",
                    choices=["store_visit", "mail_in"],
                    required=False,
                ),
            ],
        )
    elif condition == "fair":
        call.set_task(
            "present_trade_offer",
            objective=(
                f"{customer_name}'s {current_device} is in fair condition. Quote a "
                f"trade-in value of $75. Explain that fair-condition devices receive "
                f"a lower value due to wear and any functional issues, but the credit "
                f"still applies toward a new device."
            ),
            checklist=[
                guava.Say(
                    f"Based on the fair condition of your {current_device}, we can "
                    f"offer $75 in trade-in value. While devices with more wear do "
                    f"receive a lower value, this credit still applies toward any "
                    f"new device in our lineup."
                ),
                guava.Field(
                    key="interested",
                    description="Whether the customer is interested in the trade-in offer",
                    field_type="multiple_choice",
                    choices=["yes", "no", "thinking_about_it"],
                    required=True,
                ),
                guava.Field(
                    key="trade_method",
                    description="Preferred trade-in method: store visit or mail-in program",
                    field_type="multiple_choice",
                    choices=["store_visit", "mail_in"],
                    required=False,
                ),
            ],
        )
    else:
        call.set_task(
            "present_recycle_option",
            objective=(
                f"{customer_name}'s {current_device} is in poor condition. The "
                f"trade-in value is minimal ($15), but offer the free recycling "
                f"program as an alternative. Explain they can still get a new "
                f"device at full price or with any current promotions."
            ),
            checklist=[
                guava.Say(
                    f"Based on the condition of your {current_device}, the trade-in "
                    f"value would be $15. However, we do have a free device recycling "
                    f"program — we'll responsibly recycle your old device at no cost. "
                    f"And you can still take advantage of any current new device promotions."
                ),
                guava.Field(
                    key="interested",
                    description=(
                        "Whether the customer wants the minimal trade-in, free recycling, "
                        "or neither"
                    ),
                    field_type="multiple_choice",
                    choices=["trade_in", "recycle", "not_interested"],
                    required=True,
                ),
            ],
        )


@agent.on_task_complete("present_trade_offer")
def on_trade_offer_done(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    call.hangup(
        final_instructions=(
            f"Thank {customer_name} for their time. If they're interested, confirm "
            f"next steps based on their chosen method. If they chose a store visit, "
            f"let them know any Nexus Mobile location can help. If they chose mail-in, "
            f"a prepaid kit will arrive within 3 business days. If not interested, "
            f"let them know the offer stands whenever they're ready, and politely say goodbye."
        )
    )


@agent.on_task_complete("present_recycle_option")
def on_recycle_done(call: guava.Call) -> None:
    customer_name = call.get_variable("customer_name")
    call.hangup(
        final_instructions=(
            f"Thank {customer_name} for their time. If they chose recycling, let "
            f"them know a prepaid recycling kit will be sent. If not interested, "
            f"wish them well and let them know Nexus Mobile is here when they're ready, and politely say goodbye."
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
            "Let them know that a Nexus Mobile sales specialist will call them back "
            "within one business day, thank them for their time, and politely say goodbye."
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
        "account_number": call.get_variable("account_number"),
        "current_device": call.get_variable("current_device"),
        "device_condition": call.get_field("device_condition"),
        "interested": call.get_field("interested"),
        "trade_method": call.get_field("trade_method"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound device trade-in call for Nexus Mobile"
    )
    parser.add_argument("phone", help="Customer phone number to call")
    parser.add_argument("--name", required=True, help="Customer full name")
    parser.add_argument("--account-number", required=True, help="Customer account number")
    parser.add_argument(
        "--current-device", required=True, help="Make and model of the customer's current device"
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
            "account_number": args.account_number,
            "current_device": args.current_device,
        },
    )

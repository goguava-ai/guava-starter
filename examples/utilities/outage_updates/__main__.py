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
    name="Robin",
    organization="Metro Power & Light",
    purpose=(
        "notify customers about an active power outage affecting their area, "
        "provide status information and estimated restoration time, and check "
        "on any special needs during the outage"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
    "report_emergency": "The caller has a downed power line, gas leak, electrical fire, or other safety emergency",
})


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(
        contact_full_name=call.get_variable("contact_name"),
        voicemail_message=(
            f"Hi, this is Robin from Metro Power & Light calling for "
            f"{call.get_variable('contact_name')} with an outage update. "
            f"There is a power outage in your area. Please call us back "
            f"or visit metropowerandlight.com for restoration updates. "
            f"Thank you."
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    contact_name = call.get_variable("contact_name")
    account_number = call.get_variable("account_number")
    outage_cause = call.get_variable("outage_cause")
    estimated_restoration = call.get_variable("estimated_restoration")

    if outcome == "available":
        call.set_task(
            "outage_update",
            objective=(
                f"Inform {contact_name} (account {account_number}) about the "
                f"power outage caused by {outage_cause}. Power is estimated to "
                f"be restored {estimated_restoration}. Confirm they received the "
                f"update and determine their current power situation."
            ),
            checklist=[
                guava.Say(
                    f"I have a service update for your account. We are "
                    f"experiencing a power outage in your area due to "
                    f"{outage_cause}. Our crews are working to restore service "
                    f"and we estimate power will be restored "
                    f"{estimated_restoration}. We apologize for the "
                    f"inconvenience."
                ),
                guava.Field(
                    key="current_situation",
                    description=(
                        "Ask the customer about their current power situation"
                    ),
                    field_type="multiple_choice",
                    choices=["power_out", "intermittent", "restored"],
                    required=True,
                ),
            ],
        )
    elif outcome == "do_not_contact":
        logging.info("Customer %s requested no further contact.", contact_name)
        call.hangup(
            final_instructions=(
                "Acknowledge their request, let them know they will not be "
                "contacted again by phone, suggest they check outage status "
                "online at metropowerandlight.com, and politely say goodbye."
            )
        )
    elif outcome == "wrong_number":
        logging.info("Wrong number reached for %s.", contact_name)
        call.hangup(final_instructions="Apologize for the mistake and politely say goodbye.")
    else:
        logging.info("Could not reach %s (outcome: %s).", contact_name, outcome)
        call.hangup()


@agent.on_task_complete("outage_update")
def on_update_done(call: guava.Call) -> None:
    situation = call.get_field("current_situation")
    contact_name = call.get_variable("contact_name")

    if situation == "power_out":
        call.set_task(
            "power_out_support",
            objective=(
                f"{contact_name}'s power is currently out. Provide the estimated "
                f"restoration time again, share safety tips (do not use generators "
                f"indoors, keep refrigerator and freezer doors closed, use "
                f"flashlights instead of candles), and check if they need "
                f"assistance finding an alternate location."
            ),
            checklist=[
                guava.Field(
                    key="medical_equipment_dependent",
                    description=(
                        "Ask whether anyone in the household relies on electrically "
                        "powered medical equipment such as oxygen concentrators, "
                        "home dialysis machines, or other life-sustaining devices"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="generator_available",
                    description="Whether the customer has a generator or backup power source",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="alternate_location_needed",
                    description=(
                        "Whether the customer needs help finding a warming or "
                        "cooling center while power is restored"
                    ),
                    field_type="text",
                    required=False,
                ),
            ],
        )
    elif situation == "intermittent":
        call.set_task(
            "intermittent_support",
            objective=(
                f"{contact_name} is experiencing intermittent power. Walk them "
                f"through basic troubleshooting: check the breaker panel, note "
                f"whether specific circuits are affected. Let them know their "
                f"report has been filed and crews will investigate. Advise them "
                f"to unplug sensitive electronics to avoid surge damage."
            ),
            checklist=[
                guava.Field(
                    key="medical_equipment_dependent",
                    description=(
                        "Ask whether anyone in the household relies on electrically "
                        "powered medical equipment such as oxygen concentrators, "
                        "home dialysis machines, or other life-sustaining devices"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="intermittent_details",
                    description="Description of the intermittent power behavior the customer is experiencing",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="breaker_checked",
                    description="Whether the customer has checked their breaker panel",
                    field_type="multiple_choice",
                    choices=["yes", "no"],
                    required=True,
                ),
            ],
        )
    else:
        # restored
        call.hangup(
            final_instructions=(
                f"Confirm with {contact_name} that their power has been fully "
                f"restored and is working normally, thank them for their patience "
                f"during the outage, let them know they can call Metro Power & "
                f"Light if they experience any further issues, and politely "
                f"say goodbye."
            )
        )


@agent.on_task_complete("power_out_support")
def on_power_out_done(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    med_equip = call.get_field("medical_equipment_dependent")

    if med_equip and med_equip.lower() not in ("no", "none", "n/a"):
        logging.warning("Medical equipment dependency flagged for %s — priority escalation.", contact_name)
        call.hangup(
            final_instructions=(
                f"Let {contact_name} know that their household has been flagged "
                f"as a medical priority account and crews will prioritize their "
                f"area. Advise them to call 9-1-1 immediately if the situation "
                f"becomes a medical emergency. They can also reach the Metro "
                f"Power & Light medical baseline line at 1-555-100-0800 for "
                f"priority updates, and politely say goodbye."
            )
        )
        return

    call.hangup(
        final_instructions=(
            f"Thank {contact_name} for their patience and "
            f"remind them that crews are working as quickly and safely as "
            f"possible. Let them know they can track outage status at "
            f"metropowerandlight.com, and politely "
            f"say goodbye."
        )
    )


@agent.on_task_complete("intermittent_support")
def on_intermittent_done(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    med_equip = call.get_field("medical_equipment_dependent")

    if med_equip and med_equip.lower() not in ("no", "none", "n/a"):
        logging.warning("Medical equipment dependency flagged for %s — priority escalation.", contact_name)
        call.hangup(
            final_instructions=(
                f"Let {contact_name} know their intermittent power report has "
                f"been filed as a medical priority case and crews will investigate "
                f"urgently. Advise them to call 9-1-1 immediately if the situation "
                f"becomes a medical emergency. They can reach the Metro Power & "
                f"Light medical baseline line at 1-555-100-0800 for priority "
                f"updates, and politely say goodbye."
            )
        )
        return

    call.hangup(
        final_instructions=(
            f"Let {contact_name} know their intermittent "
            f"power report has been filed and crews will investigate. Advise them "
            f"to call back if the situation worsens or if they lose power entirely, "
            f"thank them for reporting the issue, and politely say goodbye."
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
            "Acknowledge their request and let them know they will not be "
            "contacted again by phone, and politely say goodbye."
        )
    )


@agent.on_action("report_emergency")
def handle_emergency(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            "Tell them to call 9-1-1 immediately for the downed power line, "
            "gas leak, or electrical fire, and politely say goodbye."
        )
    )


@agent.on_outbound_failed
def on_outbound_failed(event: OutboundCallFailed) -> None:
    logging.error("Outbound call failed: %s (code %d)", event.error_reason, event.error_code)


@agent.on_session_end
def on_session_end(call: guava.Call, event: BotSessionEnded) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "use_case": "outage_update",
        "contact_name": call.get_variable("contact_name"),
        "account_number": call.get_variable("account_number"),
        "outage_cause": call.get_variable("outage_cause"),
        "estimated_restoration": call.get_variable("estimated_restoration"),
        "current_situation": call.get_field("current_situation"),
        "medical_equipment_dependent": call.get_field("medical_equipment_dependent"),
        "generator_available": call.get_field("generator_available"),
        "alternate_location_needed": call.get_field("alternate_location_needed"),
        "intermittent_details": call.get_field("intermittent_details"),
        "breaker_checked": call.get_field("breaker_checked"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Metro Power & Light — Outage Update Notification"
    )
    parser.add_argument("phone", help="Customer phone number to call")
    parser.add_argument("--name", required=True, help="Customer full name")
    parser.add_argument("--account-number", required=True, help="Customer account number")
    parser.add_argument(
        "--outage-cause",
        default="an equipment issue in your area",
        help="Description of the cause of the outage",
    )
    parser.add_argument(
        "--estimated-restoration",
        default="by 6:00 PM today",
        help="Estimated power restoration time (e.g. 'by 6:00 PM today')",
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
            "account_number": args.account_number,
            "outage_cause": args.outage_cause,
            "estimated_restoration": args.estimated_restoration,
        },
    )

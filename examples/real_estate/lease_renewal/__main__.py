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
    name="Sage",
    organization="Pinnacle Property Management",
    purpose=(
        "reach out to tenants ahead of their lease expiration to determine "
        "their renewal intent, collect relevant details based on their decision, "
        "and facilitate next steps for renewal, negotiation, or move-out"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
    "speak_to_manager": "The caller wants to speak to a property manager or leasing office",
})


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(
        contact_full_name=call.get_variable("contact_name"),
        voicemail_message=(
            f"Hi, this is Sage from Pinnacle Property Management calling for "
            f"{call.get_variable('contact_name')} regarding your upcoming lease "
            f"renewal at {call.get_variable('unit_address')}. Your lease expires "
            f"{call.get_variable('expiration_date')}. Please call us back at your "
            f"earliest convenience. Thank you!"
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    contact_name = call.get_variable("contact_name")
    unit_address = call.get_variable("unit_address")
    expiration_date = call.get_variable("expiration_date")

    if outcome == "available":
        call.set_task(
            "renewal_decision",
            objective=(
                f"Call {contact_name}, a current tenant at {unit_address}, whose "
                f"lease expires {expiration_date}. Determine whether they plan to "
                f"renew, want to negotiate terms, or plan to vacate."
            ),
            checklist=[
                guava.Say(
                    f"I'm calling about your lease at {unit_address}, which is "
                    f"coming up for renewal {expiration_date}. I just have a couple "
                    f"of quick questions."
                ),
                guava.Field(
                    key="renewal_decision",
                    description="The tenant's decision about their lease renewal",
                    field_type="multiple_choice",
                    choices=["renew", "negotiate", "vacate"],
                    required=True,
                ),
            ],
        )
    elif outcome == "do_not_contact":
        logging.info("Tenant %s requested no further contact.", contact_name)
        call.hangup(
            final_instructions=(
                "Acknowledge their request. Let them know they will not be contacted "
                "again by phone. Remind them that lease renewal notices will still be "
                "sent by mail as required, and politely say goodbye."
            )
        )
    elif outcome == "wrong_number":
        logging.info("Wrong number reached for %s.", contact_name)
        call.hangup(final_instructions="Apologize for the mistake and wish them well, and politely say goodbye.")
    else:
        logging.info("Could not reach %s (outcome: %s).", contact_name, outcome)
        call.hangup()


@agent.on_task_complete("renewal_decision")
def on_renewal_decision_done(call: guava.Call) -> None:
    decision = call.get_field("renewal_decision")
    contact_name = call.get_variable("contact_name")
    unit_address = call.get_variable("unit_address")

    if decision == "renew":
        call.set_task(
            "confirm_renewal",
            objective=(
                f"{contact_name} wants to renew their lease at {unit_address}. "
                f"Confirm their preferred lease term and let them know renewal "
                f"documents will be sent for signature."
            ),
            checklist=[
                guava.Field(
                    key="preferred_lease_term",
                    description=(
                        "The tenant's preferred lease term for renewal "
                        "(6 months, 12 months, month-to-month, etc.)"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="updated_contact_info",
                    description=(
                        "Any updated email or phone number for sending renewal documents"
                    ),
                    field_type="text",
                    required=False,
                ),
            ],
        )
    elif decision == "negotiate":
        call.set_task(
            "collect_negotiation_concerns",
            objective=(
                f"{contact_name} wants to discuss lease terms before renewing at "
                f"{unit_address}. Collect their concerns and schedule a callback "
                f"from the property manager."
            ),
            checklist=[
                guava.Field(
                    key="negotiation_concerns",
                    description=(
                        "What the tenant wants to discuss or negotiate "
                        "(rent amount, lease length, maintenance issues, amenities, etc.)"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="preferred_callback_time",
                    description="When the tenant prefers to receive a callback from the manager",
                    field_type="text",
                    required=True,
                ),
            ],
        )
    else:
        call.set_task(
            "collect_moveout_details",
            objective=(
                f"{contact_name} plans to vacate {unit_address}. Collect their "
                f"planned move-out date and ask if they'd like to share their "
                f"reason for leaving. The property management team will email "
                f"them a move-out checklist and inspection scheduling details."
            ),
            checklist=[
                guava.Field(
                    key="planned_moveout_date",
                    description="The date the tenant plans to move out",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="reason_for_leaving",
                    description="The tenant's reason for not renewing (optional feedback)",
                    field_type="text",
                    required=False,
                ),
            ],
        )


@agent.on_task_complete("confirm_renewal")
def on_renewal_confirmed(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    call.hangup(
        final_instructions=(
            f"Thank {contact_name} for choosing to stay at Pinnacle Property "
            f"Management. Let them know renewal documents will be sent within "
            f"5 business days for their signature. If they provided updated "
            f"contact information, confirm it was noted, and wish them a great day, and politely say goodbye."
        )
    )


@agent.on_task_complete("collect_negotiation_concerns")
def on_negotiation_done(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    call.hangup(
        final_instructions=(
            f"Thank {contact_name} for sharing their concerns. Let them know "
            f"the property manager will call them back at their preferred time "
            f"to discuss options. Assure them Pinnacle values their tenancy and "
            f"wants to find a solution that works, and wish them well, and politely say goodbye."
        )
    )


@agent.on_task_complete("collect_moveout_details")
def on_moveout_done(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    call.hangup(
        final_instructions=(
            f"Thank {contact_name} for letting Pinnacle know. Explain that a "
            f"move-out checklist and inspection scheduling details will be emailed "
            f"to them. Remind them to submit a written notice to the leasing office "
            f"at least 30 days before their move-out date. Wish them the best in "
            f"their next chapter, and politely say goodbye."
        )
    )


@agent.on_action_request
def on_action_request(call: guava.Call, intent_summary: str):
    return _mid_call_intent.classify(intent_summary)


@agent.on_action("do_not_contact")
def handle_dnc(call: guava.Call) -> None:
    logging.info("Tenant %s requested DNC mid-call.", call.get_variable("contact_name"))
    call.hangup(
        final_instructions=(
            "Acknowledge their request. Let them know they've been removed from "
            "the call list. Remind them that lease renewal notices will still be "
            "sent by mail as required, and politely say goodbye."
        )
    )


@agent.on_action("speak_to_manager")
def handle_speak_to_manager(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            "Let them know that the property manager will call them back within "
            "one business day. Ask if there is a preferred time and thank them, and politely say goodbye."
        )
    )


@agent.on_outbound_failed
def on_outbound_failed(event: OutboundCallFailed) -> None:
    logging.error("Outbound call failed: %s (code %d)", event.error_reason, event.error_code)


@agent.on_session_end
def on_session_end(call: guava.Call, event: BotSessionEnded) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "contact_name": call.get_variable("contact_name"),
        "unit_address": call.get_variable("unit_address"),
        "expiration_date": call.get_variable("expiration_date"),
        "renewal_decision": call.get_field("renewal_decision"),
        "preferred_lease_term": call.get_field("preferred_lease_term"),
        "updated_contact_info": call.get_field("updated_contact_info"),
        "negotiation_concerns": call.get_field("negotiation_concerns"),
        "preferred_callback_time": call.get_field("preferred_callback_time"),
        "planned_moveout_date": call.get_field("planned_moveout_date"),
        "reason_for_leaving": call.get_field("reason_for_leaving"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound lease renewal call for Pinnacle Property Management"
    )
    parser.add_argument("phone", help="The tenant's phone number to call")
    parser.add_argument("--name", required=True, help="Full name of the tenant to reach")
    parser.add_argument("--unit", required=True, help="Unit address of the tenant's rental")
    parser.add_argument(
        "--expiration-date",
        default="in 60 days",
        help="Lease expiration date or description (e.g., 'on April 30th' or 'in 60 days').",
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
            "unit_address": args.unit,
            "expiration_date": args.expiration_date,
        },
    )

# SDK conformance: guava-sdk 0.44.0 (2026-09-15)
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
    name="Blake",
    organization="Metro Power & Light",
    purpose=(
        "alert customers whose energy usage is significantly above their "
        "normal patterns, understand whether the increase is expected, and "
        "offer energy efficiency resources and billing programs"
    ),
)

_mid_call_intent = IntentRecognizer({
    "do_not_contact": "The caller wants to stop receiving calls or be removed from the contact list",
    "speak_to_someone": "The caller wants to speak to a billing representative or customer service agent",
})


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.reach_person(
        contact_full_name=call.get_variable("contact_name"),
        voicemail_message=(
            f"Hi, this is Blake from Metro Power & Light calling for "
            f"{call.get_variable('contact_name')}. We noticed your energy usage "
            f"is higher than usual this month. Please call us back at your "
            f"convenience to learn about programs that can help. Thank you."
        ),
    )


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    contact_name = call.get_variable("contact_name")
    account_number = call.get_variable("account_number")
    usage_percent_above = call.get_variable("usage_percent_above")
    estimated_bill = call.get_variable("estimated_bill")

    if outcome == "available":
        call.set_task(
            "high_usage_alert",
            objective=(
                f"Speak with {contact_name} (account {account_number}) about an "
                f"unusually high energy usage pattern. Their usage is currently "
                f"{usage_percent_above}% above their normal level for this time "
                f"of year, and their estimated bill this month is {estimated_bill}. "
                f"Determine whether the customer is aware of a reason for the "
                f"increase and collect their response."
            ),
            checklist=[
                guava.Say(
                    f"I have an important update about your account. We've "
                    f"noticed that your energy usage this billing period is about "
                    f"{usage_percent_above}% higher than your typical usage for "
                    f"this time of year. Based on current usage, your estimated "
                    f"bill this month is approximately {estimated_bill}. We "
                    f"wanted to reach out so this doesn't come as a surprise."
                ),
                guava.Field(
                    key="customer_response",
                    description=(
                        "Ask whether the customer was aware of the higher usage "
                        "and how they would like to proceed"
                    ),
                    field_type="multiple_choice",
                    choices=["acknowledge", "dispute_reading", "request_audit"],
                    required=True,
                ),
                guava.Field(
                    key="known_reason_for_increase",
                    description=(
                        "Ask whether the customer knows what may have caused the "
                        "increase, such as new appliances, houseguests, extreme "
                        "weather, a new electric vehicle, or changes to their home"
                    ),
                    field_type="text",
                    required=False,
                ),
            ],
        )
    elif outcome == "do_not_contact":
        logging.info("Customer %s requested no further contact.", contact_name)
        call.hangup(
            final_instructions=(
                "Acknowledge their request. Let them know they will not be "
                "contacted again by phone. Suggest they check their account "
                "online for usage details, and politely say goodbye."
            )
        )
    elif outcome == "wrong_number":
        logging.info("Wrong number reached for %s.", contact_name)
        call.hangup(final_instructions="Apologize for the mistake and wish them well, and politely say goodbye.")
    else:
        logging.info("Could not reach %s (outcome: %s).", contact_name, outcome)
        call.hangup()


@agent.on_task_complete("high_usage_alert")
def on_alert_done(call: guava.Call) -> None:
    response = call.get_field("customer_response")
    contact_name = call.get_variable("contact_name")

    if response == "acknowledge":
        call.set_task(
            "energy_saving_tips",
            objective=(
                f"{contact_name} acknowledged the high usage. Mention available "
                f"programs: a free home energy audit, paperless billing with "
                f"usage alerts, and budget billing that averages costs over "
                f"12 months."
            ),
            checklist=[
                guava.Field(
                    key="interested_in_energy_audit",
                    description=(
                        "Whether the customer would like a free home energy audit "
                        "where a specialist identifies ways to reduce consumption"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="budget_billing_interest",
                    description=(
                        "Whether the customer is interested in budget billing, "
                        "which averages energy costs over 12 months for predictable "
                        "monthly payments"
                    ),
                    field_type="text",
                    required=False,
                ),
            ],
        )
    elif response == "dispute_reading":
        call.set_task(
            "dispute_info",
            objective=(
                f"{contact_name} wants to dispute their meter reading. Explain "
                f"how to request a formal meter accuracy review. The customer can "
                f"submit a request online, by phone, or in writing. A technician "
                f"will test the meter within 10 business days and provide results."
            ),
            checklist=[
                guava.Field(
                    key="dispute_details",
                    description="Why the customer believes the reading may be inaccurate",
                    field_type="text",
                    required=True,
                ),
            ],
        )
    else:
        # request_audit
        call.set_task(
            "schedule_audit",
            objective=(
                f"{contact_name} would like to request a meter audit. Collect "
                f"their scheduling preferences for the audit appointment. A "
                f"technician will visit to test the meter at no charge."
            ),
            checklist=[
                guava.Field(
                    key="audit_date_preference",
                    description="When the customer would like the meter audit scheduled",
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="audit_time_preference",
                    description="Preferred time window for the meter audit",
                    field_type="multiple_choice",
                    choices=["Morning (8 AM to 12 PM)", "Afternoon (12 PM to 5 PM)", "Any time"],
                    required=True,
                ),
            ],
        )


@agent.on_task_complete("energy_saving_tips")
def on_tips_done(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            f"Summarize any programs {call.get_variable('contact_name')} expressed "
            f"interest in and let them know a follow-up confirmation will be sent. "
            f"Remind them they can monitor usage through their online account or "
            f"the Metro Power & Light app, and thank them for their time, and politely say goodbye."
        )
    )


@agent.on_task_complete("dispute_info")
def on_dispute_done(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            f"Let {call.get_variable('contact_name')} know their dispute has been "
            f"noted and a meter accuracy review will be scheduled. Results are "
            f"typically available within 10 business days. Let them know they can "
            f"call Metro Power & Light if they have follow-up questions, and "
            f"thank them, and politely say goodbye."
        )
    )


@agent.on_task_complete("schedule_audit")
def on_audit_done(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            f"Confirm the audit appointment details with "
            f"{call.get_variable('contact_name')}. Let them know a technician "
            f"will visit at no charge and someone 18 or older should be present. "
            f"A confirmation will be sent, and thank them for their time, and politely say goodbye."
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
            "again by phone, and wish them well, and politely say goodbye."
        )
    )


@agent.on_action("speak_to_someone")
def handle_speak_to_someone(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            "Let them know that a Metro Power & Light representative will call "
            "them back within one business day. Ask if there's a preferred time "
            "and thank them for their patience, and politely say goodbye."
        )
    )


@agent.on_outbound_failed
def on_outbound_failed(event: OutboundCallFailed) -> None:
    logging.error("Outbound call failed: %s (code %d)", event.error_reason, event.error_code)


@agent.on_session_end
def on_session_end(call: guava.Call, event: BotSessionEnded) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "use_case": "high_usage_alert",
        "contact_name": call.get_variable("contact_name"),
        "account_number": call.get_variable("account_number"),
        "usage_percent_above": call.get_variable("usage_percent_above"),
        "estimated_bill": call.get_variable("estimated_bill"),
        "customer_response": call.get_field("customer_response"),
        "known_reason_for_increase": call.get_field("known_reason_for_increase"),
        "interested_in_energy_audit": call.get_field("interested_in_energy_audit"),
        "budget_billing_interest": call.get_field("budget_billing_interest"),
        "dispute_details": call.get_field("dispute_details"),
        "audit_date_preference": call.get_field("audit_date_preference"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Metro Power & Light — High Usage Alert Outbound Call"
    )
    parser.add_argument("phone", help="Customer phone number to call")
    parser.add_argument("--name", required=True, help="Customer full name")
    parser.add_argument("--account-number", required=True, help="Customer account number")
    parser.add_argument(
        "--usage-percent-above",
        required=True,
        help="Percentage above normal usage (e.g. '47')",
    )
    parser.add_argument(
        "--estimated-bill",
        required=True,
        help="Estimated bill amount this month (e.g. '$284')",
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
            "usage_percent_above": args.usage_percent_above,
            "estimated_bill": args.estimated_bill,
        },
    )

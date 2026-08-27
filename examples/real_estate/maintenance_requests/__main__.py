# SDK conformance: guava-sdk 0.39.0 (2026-08-26)
import argparse
import json
import logging
from datetime import datetime, timezone

import guava
from guava import logging_utils
from guava.helpers.llm import IntentRecognizer
from guava.events import BotSessionEnded, OutboundCallFailed


# ---------------------------------------------------------------------------
# Mock API — simulates tenant lookup and work order creation
# ---------------------------------------------------------------------------

MOCK_TENANTS = {
    "12A": {
        "tenant_name": "Maria Santos",
        "phone": "+15559001001",
        "lease_status": "active",
    },
    "7B": {
        "tenant_name": "David Park",
        "phone": "+15559001002",
        "lease_status": "active",
    },
    "3C": {
        "tenant_name": "Rachel Kim",
        "phone": "+15559001003",
        "lease_status": "active",
    },
}

EMERGENCY_MAINTENANCE_LINE = "+15554000100"


def lookup_tenant(unit_number, tenant_name):
    tenant = MOCK_TENANTS.get(unit_number)
    if tenant and tenant["tenant_name"].lower() == tenant_name.lower():
        return tenant
    return None


def create_work_order(unit_number, category, urgency, description):
    wo_number = f"WO-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    logging.info(
        "[MOCK API] POST /work-orders — created %s for unit %s (%s, %s)",
        wo_number, unit_number, category, urgency,
    )
    return wo_number


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

agent = guava.Agent(
    name="Quinn",
    organization="Pinnacle Property Management - Maintenance",
    purpose=(
        "identify tenants calling with maintenance issues, classify and triage "
        "the urgency, create work orders, and dispatch emergency maintenance "
        "when needed"
    ),
)

_mid_call_intent = IntentRecognizer({
    "speak_to_maintenance": "The caller wants to speak to a maintenance supervisor or live person",
    "withdraw": "The caller wants to stop the process, hang up, or call back later",
})


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "identify_tenant",
        objective=(
            "Identify the tenant before collecting maintenance details. "
            "Collect their unit number and name. Do not proceed with the "
            "maintenance request until the tenant is verified."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling Pinnacle Property Management maintenance "
                "line. I'm here to help you log a maintenance request and get the "
                "right team on it. First, let me verify your information."
            ),
            guava.Field(
                key="unit_number",
                description="The tenant's unit number (e.g., 12A, 7B)",
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="tenant_name",
                description="The tenant's full name as it appears on the lease",
                field_type="text",
                required=True,
            ),
        ],
    )


@agent.on_task_complete("identify_tenant")
def on_tenant_identified(call: guava.Call) -> None:
    unit_number = call.get_field("unit_number")
    tenant_name = call.get_field("tenant_name")
    tenant = lookup_tenant(unit_number, tenant_name)

    if tenant is None:
        logging.warning("Tenant verification failed for unit %s, name %s.", unit_number, tenant_name)
        call.hangup(
            final_instructions=(
                "Let the caller know that the name and unit number provided do "
                "not match our records. For security, you cannot proceed. Suggest "
                "they call the leasing office during business hours with their "
                "lease agreement handy, and politely say goodbye."
            )
        )
        return

    call.set_variable("unit_number", unit_number)
    call.set_variable("tenant_name", tenant["tenant_name"])

    call.add_info("verified_tenant", {
        "unit_number": unit_number,
        "tenant_name": tenant["tenant_name"],
        "lease_status": tenant["lease_status"],
    })

    call.set_task(
        "classify_issue",
        objective=(
            f"Tenant verified — {tenant['tenant_name']} in unit {unit_number}. "
            f"Collect the maintenance issue details and classify its urgency. "
            f"IMPORTANT: If the tenant reports a gas leak, instruct them to leave "
            f"the unit immediately and call 9-1-1. Do not keep them on the line."
        ),
        checklist=[
            guava.Say(
                f"Thank you, {tenant['tenant_name']}. You're verified. Now let me "
                f"get the details about your maintenance issue."
            ),
            guava.Field(
                key="issue_category",
                description="The category of the maintenance issue",
                field_type="multiple_choice",
                choices=["plumbing", "electrical", "hvac", "appliance", "structural", "pest", "other"],
                required=True,
            ),
            guava.Field(
                key="issue_description",
                description=(
                    "A detailed description of the problem — when it started, "
                    "what it looks like, and whether it has gotten worse"
                ),
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="urgency",
                description=(
                    "The urgency level of the issue. Emergency means immediate "
                    "safety or habitability risk (water leak, gas smell, no heat "
                    "in winter). Urgent means needs attention within 24 hours "
                    "(broken appliance, plumbing issue). Routine means can be "
                    "scheduled within the next week (cosmetic, minor repair)."
                ),
                field_type="multiple_choice",
                choices=["emergency", "urgent", "routine"],
                required=True,
            ),
        ],
    )


@agent.on_task_complete("classify_issue")
def on_issue_classified(call: guava.Call) -> None:
    urgency = call.get_field("urgency")
    category = call.get_field("issue_category")
    unit_number = call.get_variable("unit_number")
    tenant_name = call.get_variable("tenant_name")
    description = call.get_field("issue_description")

    # Gas leak safety check — critical path
    desc_lower = (description or "").lower()
    if "gas" in desc_lower and ("leak" in desc_lower or "smell" in desc_lower):
        logging.warning("GAS LEAK reported in unit %s. Instructing 9-1-1.", unit_number)
        call.hangup(
            final_instructions=(
                f"CRITICAL SAFETY: {tenant_name} has reported a possible gas leak "
                f"in unit {unit_number}. Instruct them to leave the unit immediately "
                f"and call 9-1-1 once they are safely outside. Do NOT keep them on the "
                f"line — their safety is the priority. Let them know Pinnacle will "
                f"follow up once emergency services have cleared the unit, and politely say goodbye."
            )
        )
        return

    wo_number = create_work_order(unit_number, category, urgency, description)
    call.set_variable("work_order_number", wo_number)

    if urgency == "emergency":
        call.transfer(
            destination=EMERGENCY_MAINTENANCE_LINE,
            instructions=(
                f"Tenant {tenant_name} in unit {unit_number} has an emergency "
                f"maintenance issue: {category}. Work order {wo_number} has been "
                f"created. Let them know you're connecting them with emergency "
                f"maintenance for immediate dispatch. Reassure them help is on "
                f"the way."
            ),
        )
    elif urgency == "urgent":
        call.set_task(
            "schedule_urgent",
            objective=(
                f"Work order {wo_number} created for urgent {category} issue in "
                f"unit {unit_number}. Schedule a next-day visit. Collect the "
                f"tenant's availability and entry permission."
            ),
            checklist=[
                guava.Field(
                    key="available_times",
                    description=(
                        "When the tenant is available for a technician visit "
                        "tomorrow (morning, afternoon, or specific time)"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="permission_to_enter",
                    description=(
                        "Whether Pinnacle has permission to enter the unit with "
                        "proper notice if the tenant is not home"
                    ),
                    field_type="multiple_choice",
                    choices=["yes", "no"],
                    required=True,
                ),
            ],
        )
    else:
        call.set_task(
            "schedule_routine",
            objective=(
                f"Work order {wo_number} created for routine {category} issue in "
                f"unit {unit_number}. Schedule a standard maintenance visit within "
                f"the next 3 to 5 business days."
            ),
            checklist=[
                guava.Field(
                    key="preferred_days",
                    description=(
                        "The tenant's preferred days for a maintenance visit "
                        "(weekday mornings, weekday afternoons, weekends, etc.)"
                    ),
                    field_type="text",
                    required=True,
                ),
                guava.Field(
                    key="permission_to_enter",
                    description=(
                        "Whether Pinnacle has permission to enter the unit with "
                        "proper notice if the tenant is not home"
                    ),
                    field_type="multiple_choice",
                    choices=["yes", "no"],
                    required=True,
                ),
            ],
        )


@agent.on_task_complete("schedule_urgent")
def on_urgent_scheduled(call: guava.Call) -> None:
    tenant_name = call.get_variable("tenant_name")
    wo_number = call.get_variable("work_order_number")
    call.hangup(
        final_instructions=(
            f"Let {tenant_name} know their work order number is {wo_number}. "
            f"A technician will be dispatched within 24 hours at the time they "
            f"indicated. They will receive a confirmation text. Remind them they "
            f"can call back with their work order number for status updates. "
            f"Thank them for calling, and politely say goodbye."
        )
    )


@agent.on_task_complete("schedule_routine")
def on_routine_scheduled(call: guava.Call) -> None:
    tenant_name = call.get_variable("tenant_name")
    wo_number = call.get_variable("work_order_number")
    call.hangup(
        final_instructions=(
            f"Let {tenant_name} know their work order number is {wo_number}. "
            f"A technician will be scheduled within 3 to 5 business days based "
            f"on their preferred availability. They will receive a confirmation "
            f"text with the scheduled date. Remind them they can call back with "
            f"the work order number for updates. Thank them, and politely say goodbye."
        )
    )


@agent.on_question
def on_question(call: guava.Call, question: str) -> str:
    return (
        "I can help with logging your maintenance request and getting the right "
        "team dispatched. For questions about lease terms, billing, or other "
        "matters, please contact the leasing office during business hours."
    )


@agent.on_action_request
def on_action_request(call: guava.Call, intent_summary: str):
    return _mid_call_intent.classify(intent_summary)


@agent.on_action("speak_to_maintenance")
def handle_transfer(call: guava.Call) -> None:
    call.transfer(
        destination=EMERGENCY_MAINTENANCE_LINE,
        instructions=(
            "Let the caller know you're connecting them with the maintenance "
            "team now. Reassure them that any information collected so far has "
            "been saved."
        ),
    )


@agent.on_action("withdraw")
def handle_withdraw(call: guava.Call) -> None:
    call.hangup(
        final_instructions=(
            "Let them know that's fine. They can call back anytime to log a "
            "maintenance request. If it is an emergency, remind them to call "
            "9-1-1 for immediate safety concerns, and wish them well, and politely say goodbye."
        )
    )


@agent.on_session_end
def on_session_end(call: guava.Call, event: BotSessionEnded) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "use_case": "maintenance_request",
        "tenant_name": call.get_variable("tenant_name"),
        "unit_number": call.get_variable("unit_number"),
        "work_order_number": call.get_variable("work_order_number"),
        "issue_category": call.get_field("issue_category"),
        "issue_description": call.get_field("issue_description"),
        "urgency": call.get_field("urgency"),
        "available_times": call.get_field("available_times"),
        "preferred_days": call.get_field("preferred_days"),
        "permission_to_enter": call.get_field("permission_to_enter"),
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
    }
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    logging_utils.configure_logging()

    parser = argparse.ArgumentParser(
        description="Inbound maintenance request agent for Pinnacle Property Management"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--phone", metavar="PHONE_NUMBER", nargs="?", const="", help="Listen for phone calls."
    )
    group.add_argument(
        "--webrtc", metavar="WEBRTC_CODE", nargs="?", const="", help="Listen on a WebRTC code."
    )
    group.add_argument("--local", action="store_true", help="Start a local call.")
    group.add_argument("--sip", metavar="SIP_CODE", help="Listen on a SIP code 'guavasip-...'.")
    group.add_argument(
        "--call", metavar="PHONE_NUMBER", help="Place an outbound call for testing."
    )
    parser.add_argument(
        "--from-number", metavar="FROM_NUMBER", help="Caller ID for --call mode."
    )
    args = parser.parse_args()

    if args.call:
        agent.call_phone(args.from_number or "", args.call)
    elif args.phone is not None:
        agent.listen_phone(args.phone)
    elif args.webrtc is not None:
        agent.listen_webrtc(args.webrtc or None)
    elif args.sip:
        agent.listen_sip(args.sip)
    else:
        agent.call_local()

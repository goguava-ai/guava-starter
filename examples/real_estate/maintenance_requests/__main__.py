import argparse
import json
import logging
import os
from datetime import datetime, timezone

import guava
from guava import logging_utils

agent = guava.Agent(
    name="Sam",
    organization="Pinnacle Property Management",
    purpose=(
        "collect detailed maintenance request information from tenants "
        "and create structured work orders so the right technician can "
        "be dispatched as quickly as possible"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "maintenance_request",
        objective=(
            "Answer the tenant's call warmly and professionally. "
            "Reassure them that their issue will be handled promptly. "
            "Gather all the information needed to create a complete work order, "
            "including the nature of the problem, how urgent it is, and the best "
            "way to coordinate entry to their unit. Be empathetic — maintenance "
            "issues can be stressful for tenants."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling Pinnacle Property Management maintenance line. "
                "My name is Sam, and I'm here to help you log your maintenance request "
                "and get the right team on it as soon as possible."
            ),
            guava.Field(
                key="tenant_name",
                description="Can I start with your full name, please?",
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="unit_address",
                description=(
                    "What is the full address of your unit, including the unit number?"
                ),
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="issue_category",
                description=(
                    "What category best describes the issue? "
                    "Options are: plumbing, electrical, HVAC, appliance, structural, or other."
                ),
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="issue_description",
                description=(
                    "Please describe the problem in as much detail as possible. "
                    "When did it start, what does it look like, and has it gotten worse?"
                ),
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="urgency_level",
                description=(
                    "How urgent is this issue? "
                    "Emergency means an immediate safety or habitability risk, "
                    "urgent means it needs attention within 24 to 48 hours, "
                    "and routine means it can be scheduled within the next week."
                ),
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="best_entry_time",
                description=(
                    "What days and times work best for a technician to access your unit? "
                    "For example, weekday mornings or weekend afternoons."
                ),
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="permission_to_enter",
                description=(
                    "Do you give Pinnacle Property Management permission to enter your unit "
                    "with proper notice to perform the repair, even if you are not present?"
                ),
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="contact_phone",
                description=(
                    "What is the best phone number to reach you for updates or to "
                    "coordinate the technician's arrival?"
                ),
                field_type="text",
                required=True,
            ),
        ],
    )


@agent.on_task_complete("maintenance_request")
def on_done(call: guava.Call) -> None:
    urgency = (call.get_field("urgency_level") or "").lower()
    if "emergency" in urgency:
        response_time = "within 2 to 4 hours"
    elif "urgent" in urgency:
        response_time = "within 24 to 48 hours"
    else:
        response_time = "within 3 to 5 business days"

    work_order_number = f"WO-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "vertical": "real_estate",
        "use_case": "maintenance_request",
        "work_order_number": work_order_number,
        "fields": {
            "tenant_name": call.get_field("tenant_name"),
            "unit_address": call.get_field("unit_address"),
            "issue_category": call.get_field("issue_category"),
            "issue_description": call.get_field("issue_description"),
            "urgency_level": call.get_field("urgency_level"),
            "best_entry_time": call.get_field("best_entry_time"),
            "permission_to_enter": call.get_field("permission_to_enter"),
            "contact_phone": call.get_field("contact_phone"),
        },
        "estimated_response_time": response_time,
    }
    print(json.dumps(results, indent=2))
    logging.info("Maintenance request work order created: %s", results)
    call.hangup(
        final_instructions=(
            f"Thank the tenant for calling in. Let them know their work order number "
            f"is {work_order_number} and that based on the urgency level they indicated, "
            f"they can expect a response {response_time}. "
            "Remind them they can call back with this work order number to check on status. "
            "If it is an emergency involving gas, water flooding, or electrical hazards, "
            "remind them to call 911 if there is any immediate danger to safety. "
            "Thank them and end the call warmly."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    logging.info("Starting Maintenance Request inbound agent for Pinnacle Property Management.")
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])

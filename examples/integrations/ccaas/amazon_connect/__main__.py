import json
import logging
import os
from datetime import datetime, timezone

import boto3
import guava
from guava import logging_utils

agent = guava.Agent(
    name="Sam",
    organization="CloudFirst Solutions - Technical Support",
    purpose=(
        "to triage inbound technical support calls, collect issue details, "
        "and create follow-up tasks so a specialist can resolve the problem"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "save_results",
        objective=(
            "A customer has called CloudFirst Solutions with a technical issue. "
            "Greet them, collect detailed information about the problem, and let "
            "them know a specialist will follow up."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling CloudFirst Solutions Technical Support. My name "
                "is Sam and I'll help get your issue to the right specialist. Let me "
                "collect some details first."
            ),
            guava.Field(
                key="caller_name",
                description="Ask the caller for their full name.",
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="phone_number",
                description=(
                    "Ask the caller for the best phone number to reach them for a "
                    "callback. Confirm the number back to them."
                ),
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="issue_category",
                description=(
                    "Ask the caller to describe their technical issue. Categorize it as: "
                    "connectivity, performance, authentication, data_loss, configuration, "
                    "or other."
                ),
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="issue_description",
                description=(
                    "Ask the caller to describe the issue in detail — what happened, "
                    "when it started, and what they were trying to do. Capture a thorough summary."
                ),
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="severity",
                description=(
                    "Assess the severity based on impact. Categorize as: critical "
                    "(system down), high (major feature broken), medium (partial impact), "
                    "or low (minor inconvenience)."
                ),
                field_type="text",
                required=True,
            ),
            guava.Field(
                key="steps_already_tried",
                description=(
                    "Ask the caller if they've already tried anything to fix the issue — "
                    "rebooting, clearing cache, reinstalling, etc. Capture what they've attempted."
                ),
                field_type="text",
                required=False,
            ),
        ],
    )


@agent.on_task_complete("save_results")
def on_done(call: guava.Call) -> None:
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": "Sam",
        "organization": "CloudFirst Solutions - Technical Support",
        "use_case": "inbound_tech_support",
        "fields": {
            "caller_name": call.get_field("caller_name"),
            "phone_number": call.get_field("phone_number"),
            "issue_category": call.get_field("issue_category"),
            "issue_description": call.get_field("issue_description"),
            "severity": call.get_field("severity"),
            "steps_already_tried": call.get_field("steps_already_tried"),
        },
    }
    print(json.dumps(results, indent=2))
    logging.info("Tech support triage results saved locally.")

    # Create follow-up task in Amazon Connect
    try:
        instance_id = os.environ["CONNECT_INSTANCE_ID"]
        contact_flow_id = os.environ["CONNECT_CONTACT_FLOW_ID"]

        connect_client = boto3.client("connect")

        task_name = (
            f"[{call.get_field('severity', 'medium').upper()}] "
            f"{call.get_field('issue_category', 'general')} - "
            f"{call.get_field('caller_name', 'Unknown')}"
        )

        connect_client.start_task_contact(
            InstanceId=instance_id,
            ContactFlowId=contact_flow_id,
            Name=task_name[:512],
            Description=(
                f"Customer: {call.get_field('caller_name')}\n"
                f"Phone: {call.get_field('phone_number')}\n"
                f"Category: {call.get_field('issue_category')}\n"
                f"Severity: {call.get_field('severity')}\n"
                f"Description: {call.get_field('issue_description')}\n"
                f"Steps tried: {call.get_field('steps_already_tried', 'None reported')}"
            )[:4096],
            References={
                "source": {
                    "Value": "guava_voice_agent",
                    "Type": "STRING",
                },
            },
            Attributes={
                "severity": call.get_field("severity", "medium"),
                "issue_category": call.get_field("issue_category", "other"),
                "caller_name": call.get_field("caller_name", "Unknown"),
            },
        )
        logging.info("Amazon Connect task created successfully.")
    except Exception as e:
        logging.error("Failed to create Amazon Connect task: %s", e)

    call.hangup(
        final_instructions=(
            "Let the customer know that a support task has been created and a specialist "
            "will call them back at the number they provided. Provide a reference number "
            "(you may use a placeholder like 'TASK-XXXXXX'). For critical issues, let them "
            "know the response time is within 1 hour. Thank them for calling CloudFirst "
            "Solutions and wish them a good day."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])

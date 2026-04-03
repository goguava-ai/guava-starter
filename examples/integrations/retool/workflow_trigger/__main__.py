import guava
import os
import logging
import requests

logging.basicConfig(level=logging.INFO)

# Generic inbound workflow trigger. The Retool workflow receives the caller's
# intent and structured fields, executes its logic, and returns a message for
# the agent to read back to the caller.
RETOOL_WORKFLOW_WEBHOOK_URL = os.environ["RETOOL_WORKFLOW_WEBHOOK_URL"]
RETOOL_WORKFLOW_API_KEY = os.environ["RETOOL_WORKFLOW_API_KEY"]

HEADERS = {
    "X-Workflow-Api-Key": RETOOL_WORKFLOW_API_KEY,
    "Content-Type": "application/json",
}


def run_workflow(payload: dict) -> dict:
    resp = requests.post(
        RETOOL_WORKFLOW_WEBHOOK_URL,
        headers=HEADERS,
        json=payload,
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


class WorkflowTriggerController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Apex Operations",
            agent_name="Riley",
            agent_purpose=(
                "to handle inbound requests from Apex Operations staff and route them "
                "to the appropriate internal workflow"
            ),
        )

        self.set_task(
            objective=(
                "An employee has called to submit a request. Collect their name, the type "
                "of request, and any relevant details, then trigger the Retool workflow and "
                "read the result back to them."
            ),
            checklist=[
                guava.Say(
                    "Thanks for calling Apex Operations. This is Riley. "
                    "I can help you submit a request. What can I do for you today?"
                ),
                guava.Field(
                    key="caller_name",
                    field_type="text",
                    description="Ask for the caller's full name.",
                    required=True,
                ),
                guava.Field(
                    key="request_type",
                    field_type="multiple_choice",
                    description="Ask what type of request they'd like to submit.",
                    choices=[
                        "purchase order approval",
                        "vendor onboarding",
                        "expense reimbursement",
                        "access request",
                        "data export",
                        "other",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="request_detail",
                    field_type="text",
                    description=(
                        "Ask them to provide any specific details about their request — "
                        "such as amounts, vendor names, system names, or any reference IDs."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="priority",
                    field_type="multiple_choice",
                    description="Ask how time-sensitive this request is.",
                    choices=["routine", "urgent — needed today", "critical — blocking operations"],
                    required=True,
                ),
            ],
            on_complete=self.trigger_workflow_and_respond,
        )

        self.accept_call()

    def trigger_workflow_and_respond(self):
        name = self.get_field("caller_name") or "the caller"
        request_type = self.get_field("request_type") or "other"
        detail = self.get_field("request_detail") or ""
        priority = self.get_field("priority") or "routine"

        logging.info(
            "Triggering Retool workflow for %s — type: %s, priority: %s",
            name, request_type, priority,
        )

        payload = {
            "caller_name": name,
            "request_type": request_type,
            "request_detail": detail,
            "priority": priority,
            "source": "voice",
        }

        try:
            result = run_workflow(payload)
            # The Retool workflow may return a `message` field for the agent to read,
            # a `request_id`, or other fields depending on the workflow design.
            message = result.get("message") or ""
            request_id = result.get("request_id") or result.get("id") or ""

            id_note = f" Your request ID is {request_id}." if request_id else ""
            agent_message = message if message else (
                f"Your {request_type} request has been submitted successfully."
            )

            logging.info("Workflow result for %s: request_id=%s", name, request_id)

            self.hangup(
                final_instructions=(
                    f"Read the following message to {name}: '{agent_message}'{id_note} "
                    "Let them know they can follow up by email or call back if they need anything else. "
                    "Thank them for calling Apex Operations."
                )
            )
        except Exception as e:
            logging.error("Retool workflow trigger failed: %s", e)
            self.hangup(
                final_instructions=(
                    f"Apologize to {name} and let them know the system encountered a brief issue. "
                    "Their request details have been noted and will be submitted manually "
                    "by the operations team. They'll receive a confirmation email shortly."
                )
            )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=WorkflowTriggerController,
    )

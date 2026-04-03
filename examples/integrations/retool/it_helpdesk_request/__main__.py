import guava
import os
import logging
import requests

logging.basicConfig(level=logging.INFO)

# Webhook URL and API key from the Retool Workflow editor (Trigger block → Run from API).
RETOOL_WORKFLOW_WEBHOOK_URL = os.environ["RETOOL_IT_HELPDESK_WORKFLOW_URL"]
RETOOL_WORKFLOW_API_KEY = os.environ["RETOOL_IT_HELPDESK_API_KEY"]

HEADERS = {
    "X-Workflow-Api-Key": RETOOL_WORKFLOW_API_KEY,
    "Content-Type": "application/json",
}


def trigger_helpdesk_workflow(payload: dict) -> dict:
    """Trigger the Retool IT helpdesk workflow and return the response."""
    resp = requests.post(
        RETOOL_WORKFLOW_WEBHOOK_URL,
        headers=HEADERS,
        json=payload,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


class ITHelpdeskRequestController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Acme Corp IT",
            agent_name="Sam",
            agent_purpose=(
                "to help Acme Corp employees report IT issues and open helpdesk tickets"
            ),
        )

        self.set_task(
            objective=(
                "An employee has called the IT helpdesk. Collect their information and a "
                "clear description of the issue, then create a helpdesk ticket in Retool."
            ),
            checklist=[
                guava.Say(
                    "Thank you for calling Acme Corp IT Helpdesk. This is Sam. "
                    "I'll get a ticket opened for you right away."
                ),
                guava.Field(
                    key="employee_name",
                    field_type="text",
                    description="Ask for the employee's full name.",
                    required=True,
                ),
                guava.Field(
                    key="employee_email",
                    field_type="text",
                    description="Ask for their work email address.",
                    required=True,
                ),
                guava.Field(
                    key="department",
                    field_type="text",
                    description="Ask which department they work in.",
                    required=False,
                ),
                guava.Field(
                    key="issue_category",
                    field_type="multiple_choice",
                    description=(
                        "Ask what type of IT issue they're experiencing."
                    ),
                    choices=[
                        "hardware",
                        "software or application",
                        "network or VPN",
                        "account or password",
                        "email",
                        "other",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="issue_description",
                    field_type="text",
                    description=(
                        "Ask them to describe the issue in their own words. "
                        "What happened, when did it start, and what have they already tried?"
                    ),
                    required=True,
                ),
                guava.Field(
                    key="urgency",
                    field_type="multiple_choice",
                    description=(
                        "Ask how urgently this is affecting their work."
                    ),
                    choices=["low — not blocking me", "normal — affecting my work", "high — I'm completely blocked"],
                    required=True,
                ),
            ],
            on_complete=self.submit_ticket,
        )

        self.accept_call()

    def submit_ticket(self):
        name = self.get_field("employee_name") or "Unknown Employee"
        email = self.get_field("employee_email") or ""
        department = self.get_field("department") or ""
        category = self.get_field("issue_category") or "other"
        description = self.get_field("issue_description") or ""
        urgency = self.get_field("urgency") or "normal — affecting my work"

        logging.info(
            "Submitting IT helpdesk ticket for %s (%s) — category: %s, urgency: %s",
            name, email, category, urgency,
        )

        payload = {
            "employee_name": name,
            "employee_email": email,
            "department": department,
            "issue_category": category,
            "issue_description": description,
            "urgency": urgency,
            "source": "voice",
        }

        try:
            result = trigger_helpdesk_workflow(payload)
            ticket_id = result.get("ticket_id") or result.get("id") or "pending"
            logging.info("Helpdesk ticket created via Retool workflow: %s", ticket_id)

            ticket_note = (
                f" Your ticket number is {ticket_id}." if str(ticket_id) != "pending" else ""
            )

            self.hangup(
                final_instructions=(
                    f"Let {name} know their IT helpdesk ticket has been submitted successfully.{ticket_note} "
                    "Tell them the IT team will follow up by email, and the response time depends "
                    "on urgency — high-priority tickets are typically addressed within the hour. "
                    "Thank them for calling and wish them a productive day."
                )
            )
        except Exception as e:
            logging.error("Failed to trigger Retool helpdesk workflow: %s", e)
            self.hangup(
                final_instructions=(
                    f"Apologize to {name} for a technical issue. Let them know the IT team "
                    "has been notified and will reach out by email to get a ticket opened for them. "
                    "Thank them for their patience."
                )
            )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=ITHelpdeskRequestController,
    )

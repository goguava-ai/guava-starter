import guava
import os
import logging
import requests
from datetime import datetime

logging.basicConfig(level=logging.INFO)

SN_INSTANCE = os.environ["SERVICENOW_INSTANCE"]  # e.g. "mycompany"
SN_USERNAME = os.environ["SERVICENOW_USERNAME"]
SN_PASSWORD = os.environ["SERVICENOW_PASSWORD"]

BASE_URL = f"https://{SN_INSTANCE}.service-now.com/api/now"
AUTH = (SN_USERNAME, SN_PASSWORD)
HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}

PRIORITY_MAP = {
    "critical — my business is stopped": "1",
    "high — major impact on my work": "2",
    "medium — partial impact": "3",
    "low — minor inconvenience": "4",
}


def create_csm_case(
    contact_name: str,
    contact_email: str,
    company: str,
    subject: str,
    description: str,
    priority: str,
) -> dict:
    """Creates a Customer Service Management case in ServiceNow. Returns the created record."""
    payload = {
        "short_description": subject,
        "description": description,
        "contact_name": contact_name,
        "account": company,
        "priority": priority,
        "state": "1",  # New
        "channel": "phone",
        "u_caller_email": contact_email,
    }
    resp = requests.post(
        f"{BASE_URL}/table/sn_customerservice_case",
        auth=AUTH,
        headers=HEADERS,
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("result", {})


class CaseCreationController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Vertex Corp",
            agent_name="Sam",
            agent_purpose=(
                "to help Vertex Corp customers open support cases and ensure their issues "
                "are routed to the right team as quickly as possible"
            ),
        )

        self.set_task(
            objective=(
                "A customer has called with a support issue. Greet them, collect their contact "
                "details and a thorough description of their issue, and open a support case "
                "in ServiceNow CSM."
            ),
            checklist=[
                guava.Say(
                    "Thank you for calling Vertex Corp Support. My name is Sam. "
                    "I'll collect a few details and get a case opened for you right away."
                ),
                guava.Field(
                    key="caller_name",
                    field_type="text",
                    description="Ask for the caller's full name.",
                    required=True,
                ),
                guava.Field(
                    key="caller_email",
                    field_type="text",
                    description="Ask for their email address.",
                    required=True,
                ),
                guava.Field(
                    key="company",
                    field_type="text",
                    description="Ask what company they're with.",
                    required=False,
                ),
                guava.Field(
                    key="issue_category",
                    field_type="multiple_choice",
                    description="Ask what type of issue they're experiencing.",
                    choices=[
                        "technical issue",
                        "billing or payment",
                        "account access",
                        "data or reporting",
                        "general question",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="issue_summary",
                    field_type="text",
                    description="Ask them to briefly describe the issue.",
                    required=True,
                ),
                guava.Field(
                    key="issue_detail",
                    field_type="text",
                    description=(
                        "Ask for any additional context — when it started, what they were doing, "
                        "and any error messages. Capture the full detail."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="priority",
                    field_type="multiple_choice",
                    description="Ask how urgently this is affecting their business.",
                    choices=[
                        "critical — my business is stopped",
                        "high — major impact on my work",
                        "medium — partial impact",
                        "low — minor inconvenience",
                    ],
                    required=True,
                ),
            ],
            on_complete=self.open_case,
        )

        self.accept_call()

    def open_case(self):
        name = self.get_field("caller_name") or "Unknown"
        email = self.get_field("caller_email") or ""
        company = self.get_field("company") or ""
        category = self.get_field("issue_category") or "general question"
        summary = self.get_field("issue_summary") or "Support request"
        detail = self.get_field("issue_detail") or ""
        priority_label = self.get_field("priority") or "medium — partial impact"

        priority_code = PRIORITY_MAP.get(priority_label, "3")
        subject = f"[{category.title()}] {summary}"
        description = (
            f"Caller: {name}\nEmail: {email}\nCompany: {company}\n\n"
            f"Summary: {summary}"
            + (f"\n\nDetail:\n{detail}" if detail else "")
        )

        logging.info("Creating ServiceNow CSM case for %s — priority: %s", name, priority_code)
        try:
            result = create_csm_case(name, email, company, subject, description, priority_code)
            case_number = result.get("number") or result.get("sys_id", "")
            logging.info("ServiceNow case created: %s", case_number)

            self.hangup(
                final_instructions=(
                    f"Let {name} know their support case has been opened. "
                    + (f"Their case number is {case_number}. " if case_number else "")
                    + "A specialist will review it based on the priority they selected and reach out "
                    "via the email they provided. Thank them for calling Vertex Corp."
                )
            )
        except Exception as e:
            logging.error("Failed to create ServiceNow case: %s", e)
            self.hangup(
                final_instructions=(
                    f"Apologize to {name} for a technical issue and let them know a support agent "
                    "will open a case manually and reach out to them. "
                    "Thank them for their patience."
                )
            )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=CaseCreationController,
    )

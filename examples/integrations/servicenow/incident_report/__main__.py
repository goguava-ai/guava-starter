import guava
import os
import logging
from guava import logging_utils
import requests
from datetime import datetime


SN_INSTANCE = os.environ["SERVICENOW_INSTANCE"]
SN_USERNAME = os.environ["SERVICENOW_USERNAME"]
SN_PASSWORD = os.environ["SERVICENOW_PASSWORD"]

BASE_URL = f"https://{SN_INSTANCE}.service-now.com/api/now"
AUTH = (SN_USERNAME, SN_PASSWORD)
HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}

IMPACT_MAP = {
    "entire organization": "1",
    "a department or team": "2",
    "just me": "3",
}

URGENCY_MAP = {
    "cannot work at all": "1",
    "can work with significant effort": "2",
    "minor inconvenience": "3",
}

# Priority = f(impact, urgency) per ITIL matrix — simplified here.
PRIORITY_MATRIX = {
    ("1", "1"): "1",  # Critical
    ("1", "2"): "2",  # High
    ("1", "3"): "2",
    ("2", "1"): "2",
    ("2", "2"): "3",  # Medium
    ("2", "3"): "3",
    ("3", "1"): "3",
    ("3", "2"): "4",  # Low
    ("3", "3"): "4",
}


def create_incident(
    caller_name: str,
    caller_email: str,
    short_description: str,
    description: str,
    impact: str,
    urgency: str,
    priority: str,
    category: str,
) -> dict:
    """Creates an ITIL Incident in ServiceNow. Returns the created record."""
    payload = {
        "caller_id": {"value": ""},  # Omit caller_id lookup for simplicity; set by name below
        "u_caller_name": caller_name,
        "u_caller_email": caller_email,
        "short_description": short_description,
        "description": description,
        "impact": impact,
        "urgency": urgency,
        "priority": priority,
        "category": category,
        "state": "1",  # New
        "contact_type": "phone",
    }
    resp = requests.post(
        f"{BASE_URL}/table/incident",
        auth=AUTH,
        headers=HEADERS,
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("result", {})


class IncidentReportController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Vertex Corp IT",
            agent_name="Morgan",
            agent_purpose=(
                "to help Vertex Corp employees report IT incidents quickly and ensure they are "
                "routed to the right resolver group based on impact and urgency"
            ),
        )

        self.set_task(
            objective=(
                "An employee has called the IT help desk to report an incident. Collect the "
                "details needed to open an ITIL incident record in ServiceNow, following the "
                "impact and urgency framework."
            ),
            checklist=[
                guava.Say(
                    "Thank you for calling the Vertex Corp IT Help Desk. I'm Morgan. "
                    "I'll gather some details to open an incident ticket for you right away."
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
                    description="Ask for their corporate email address.",
                    required=True,
                ),
                guava.Field(
                    key="incident_category",
                    field_type="multiple_choice",
                    description="Ask what category of incident they're reporting.",
                    choices=[
                        "software / application",
                        "hardware",
                        "network / connectivity",
                        "email / communication",
                        "security",
                        "access / permissions",
                        "other",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="incident_summary",
                    field_type="text",
                    description="Ask for a brief description of what's happening.",
                    required=True,
                ),
                guava.Field(
                    key="incident_detail",
                    field_type="text",
                    description=(
                        "Ask for more detail — when it started, any error messages, "
                        "what they were doing when it happened, and steps they've already tried."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="impact",
                    field_type="multiple_choice",
                    description="Ask how many people are affected.",
                    choices=["entire organization", "a department or team", "just me"],
                    required=True,
                ),
                guava.Field(
                    key="urgency",
                    field_type="multiple_choice",
                    description="Ask how severely their ability to work is impacted.",
                    choices=["cannot work at all", "can work with significant effort", "minor inconvenience"],
                    required=True,
                ),
            ],
            on_complete=self.file_incident,
        )

        self.accept_call()

    def file_incident(self):
        name = self.get_field("caller_name") or "Unknown"
        email = self.get_field("caller_email") or ""
        category_label = self.get_field("incident_category") or "other"
        summary = self.get_field("incident_summary") or "IT incident"
        detail = self.get_field("incident_detail") or ""
        impact_label = self.get_field("impact") or "just me"
        urgency_label = self.get_field("urgency") or "minor inconvenience"

        impact = IMPACT_MAP.get(impact_label, "3")
        urgency = URGENCY_MAP.get(urgency_label, "3")
        priority = PRIORITY_MATRIX.get((impact, urgency), "3")

        category_map = {
            "software / application": "software",
            "hardware": "hardware",
            "network / connectivity": "network",
            "email / communication": "email",
            "security": "security",
            "access / permissions": "access",
            "other": "inquiry",
        }
        category = category_map.get(category_label, "inquiry")

        description = (
            f"Reported by: {name} ({email})\n"
            f"Summary: {summary}"
            + (f"\n\nDetail:\n{detail}" if detail else "")
        )

        logging.info(
            "Creating ServiceNow incident for %s — impact: %s, urgency: %s, priority: %s",
            name, impact, urgency, priority,
        )
        try:
            result = create_incident(name, email, summary, description, impact, urgency, priority, category)
            incident_number = result.get("number") or result.get("sys_id", "")
            logging.info("ServiceNow incident created: %s", incident_number)

            sla_note = {
                "1": "A technician will respond within 15 minutes.",
                "2": "A technician will respond within 1 hour.",
                "3": "A technician will respond within 4 hours.",
                "4": "A technician will follow up within one business day.",
            }.get(priority, "A technician will be in touch shortly.")

            self.hangup(
                final_instructions=(
                    f"Let {name} know their incident has been logged. "
                    + (f"The incident number is {incident_number}. " if incident_number else "")
                    + f"{sla_note} "
                    "Thank them for calling the Vertex Corp IT Help Desk."
                )
            )
        except Exception as e:
            logging.error("Failed to create ServiceNow incident: %s", e)
            self.hangup(
                final_instructions=(
                    f"Apologize to {name} for a technical issue. Ask them to email "
                    "helpdesk@vertexcorp.com with their issue details, or try calling back. "
                    "Thank them for their patience."
                )
            )


if __name__ == "__main__":
    logging_utils.configure_logging()
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=IncidentReportController,
    )

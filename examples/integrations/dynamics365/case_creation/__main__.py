import guava
import os
import logging
from guava import logging_utils
import requests
from datetime import datetime, timezone


ACCESS_TOKEN = os.environ["DYNAMICS_ACCESS_TOKEN"]
ORG_URL = os.environ["DYNAMICS_ORG_URL"]  # e.g. https://yourorg.crm.dynamics.com

_BASE_HEADERS = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json",
    "OData-MaxVersion": "4.0",
    "OData-Version": "4.0",
    "Accept": "application/json",
}
HEADERS = {**_BASE_HEADERS, "Prefer": "return=representation"}  # for POST/PATCH that return data
GET_HEADERS = _BASE_HEADERS  # for GET requests

API_BASE = f"{ORG_URL}/api/data/v9.2"

PRIORITY_MAP = {
    "high": 1,
    "normal": 2,
    "low": 3,
}


def find_contact_by_email(email: str) -> dict | None:
    """Searches Dynamics 365 for a contact by email address. Returns the contact object or None."""
    resp = requests.get(
        f"{API_BASE}/contacts",
        headers=GET_HEADERS,
        params={
            "$filter": f"emailaddress1 eq '{email}'",
            "$select": "contactid,fullname,emailaddress1,telephone1,accountid",
        },
        timeout=10,
    )
    resp.raise_for_status()
    results = resp.json().get("value", [])
    return results[0] if results else None


def create_contact(first_name: str, last_name: str, email: str) -> dict:
    """Creates a new contact record in Dynamics 365 and returns it."""
    payload = {
        "firstname": first_name,
        "lastname": last_name,
        "emailaddress1": email,
    }
    resp = requests.post(f"{API_BASE}/contacts", headers=HEADERS, json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json()


def create_case(title: str, description: str, prioritycode: int, contact_id: str) -> dict:
    """Creates a new support case (incident) in Dynamics 365 and returns the created record."""
    payload = {
        "title": title,
        "description": description,
        "prioritycode": prioritycode,
        "caseorigincode": 3,   # Phone
        "casetypecode": 1,
        "customerid_contact@odata.bind": f"/contacts({contact_id})",
    }
    resp = requests.post(f"{API_BASE}/incidents", headers=HEADERS, json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json()


def add_case_note(incident_id: str, subject: str, note_text: str) -> None:
    """Posts an internal note (annotation) to an incident record."""
    payload = {
        "subject": subject,
        "notetext": note_text,
        "objectid_incident@odata.bind": f"/incidents({incident_id})",
        "objecttypecode": "incident",
    }
    resp = requests.post(f"{API_BASE}/annotations", headers=HEADERS, json=payload, timeout=10)
    resp.raise_for_status()


class CaseCreationController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Pinnacle Solutions",
            agent_name="Jordan",
            agent_purpose="to help customers report issues and open support cases with Pinnacle Solutions",
        )

        self.set_task(
            objective=(
                "A customer has called Pinnacle Solutions support. Greet them, collect their "
                "contact information and a clear description of their issue so we can open a "
                "support case in our system."
            ),
            checklist=[
                guava.Say(
                    "Thank you for calling Pinnacle Solutions support. My name is Jordan. "
                    "I'm here to help you today. I'll collect some information and open a "
                    "support case for you right away."
                ),
                guava.Field(
                    key="caller_name",
                    field_type="text",
                    description="Ask the caller for their full name — first and last.",
                    required=True,
                ),
                guava.Field(
                    key="caller_email",
                    field_type="text",
                    description="Ask for their email address so we can send case updates.",
                    required=True,
                ),
                guava.Field(
                    key="issue_type",
                    field_type="multiple_choice",
                    description=(
                        "Ask what type of issue they are experiencing. "
                        "Map their answer to the closest category."
                    ),
                    choices=["billing", "technical", "account", "product-feedback", "other"],
                    required=True,
                ),
                guava.Field(
                    key="issue_summary",
                    field_type="text",
                    description=(
                        "Ask the caller to briefly describe the issue they are experiencing. "
                        "Capture a clear one-sentence summary."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="issue_detail",
                    field_type="text",
                    description=(
                        "Ask for any additional details — what they were doing when it happened, "
                        "any error messages, and how long it has been occurring."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="priority",
                    field_type="multiple_choice",
                    description=(
                        "Ask how urgently this is affecting their work. "
                        "Map their answer to a priority level."
                    ),
                    choices=["low", "normal", "high"],
                    required=True,
                ),
            ],
            on_complete=self.open_case,
        )

        self.accept_call()

    def open_case(self):
        name = self.get_field("caller_name") or "Unknown Caller"
        email = self.get_field("caller_email") or ""
        issue_type = self.get_field("issue_type") or "other"
        summary = self.get_field("issue_summary") or "Support request"
        detail = self.get_field("issue_detail") or ""
        priority = self.get_field("priority") or "normal"

        prioritycode = PRIORITY_MAP.get(priority, 2)

        description = summary
        if detail:
            description = f"{summary}\n\nAdditional details:\n{detail}"

        # Split name into first/last for contact creation
        name_parts = name.strip().split(" ", 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        logging.info(
            "Opening case for %s (%s) — type: %s, priority: %s", name, email, issue_type, priority
        )

        try:
            # Look up or create the contact
            contact = find_contact_by_email(email) if email else None
            if contact:
                contact_id = contact["contactid"]
                logging.info("Found existing contact %s", contact_id)
            else:
                logging.info("Contact not found for %s — creating new record", email)
                contact = create_contact(first_name, last_name, email)
                contact_id = contact["contactid"]
                logging.info("Created contact %s", contact_id)

            # Create the case
            case_title = f"[{issue_type.title()}] {summary}"
            case = create_case(
                title=case_title,
                description=description,
                prioritycode=prioritycode,
                contact_id=contact_id,
            )
            incident_id = case["incidentid"]
            ticket_number = case.get("ticketnumber", incident_id)
            logging.info("Created case %s (%s)", ticket_number, incident_id)

            # Add internal note with caller context
            note_text = (
                f"Case opened via voice call — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n"
                f"Caller: {name}\n"
                f"Email: {email}\n"
                f"Issue type: {issue_type}\n"
                f"Priority: {priority}\n"
                f"Summary: {summary}"
            )
            if detail:
                note_text += f"\nDetail: {detail}"

            add_case_note(incident_id, "Voice call — case opened", note_text)
            logging.info("Internal note added to case %s", ticket_number)

            self.hangup(
                final_instructions=(
                    f"Let {name} know their support case has been created successfully. "
                    f"Their case number is {ticket_number}. "
                    "Tell them they will receive a confirmation email shortly and our team will "
                    "be in touch based on the priority they selected. "
                    "Thank them for calling Pinnacle Solutions."
                )
            )

        except Exception as e:
            logging.error("Failed to create case for %s: %s", name, e)
            self.hangup(
                final_instructions=(
                    f"Apologize to {name} for a technical issue and let them know a support "
                    "agent will follow up by email to manually open their case. "
                    "Thank them for their patience."
                )
            )


if __name__ == "__main__":
    logging_utils.configure_logging()
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=CaseCreationController,
    )

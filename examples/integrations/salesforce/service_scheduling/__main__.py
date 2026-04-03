import guava
import os
import logging
import requests
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)

SALESFORCE_INSTANCE_URL = os.environ["SALESFORCE_INSTANCE_URL"]
SALESFORCE_ACCESS_TOKEN = os.environ["SALESFORCE_ACCESS_TOKEN"]
SF_HEADERS = {
    "Authorization": f"Bearer {SALESFORCE_ACCESS_TOKEN}",
    "Content-Type": "application/json",
}
API_BASE = f"{SALESFORCE_INSTANCE_URL}/services/data/v66.0"

# Map caller-described time slots to UTC offsets for demo purposes.
# In production, resolve these against real calendar availability.
SLOT_OFFSETS_DAYS = {
    "tomorrow morning": (1, 9),
    "tomorrow afternoon": (1, 14),
    "day after tomorrow morning": (2, 9),
    "day after tomorrow afternoon": (2, 14),
    "next monday morning": (7, 9),
    "next monday afternoon": (7, 14),
}


def find_contact_by_email(email: str) -> dict | None:
    q = f"SELECT Id, FirstName, LastName, AccountId FROM Contact WHERE Email = '{email}' LIMIT 1"
    resp = requests.get(
        f"{API_BASE}/query",
        headers=SF_HEADERS,
        params={"q": q},
        timeout=10,
    )
    resp.raise_for_status()
    records = resp.json().get("records", [])
    return records[0] if records else None


def create_event(contact_id: str, account_id: str, subject: str, description: str, slot_key: str) -> str:
    """Creates a Salesforce Event for the given contact and account. Returns the event ID."""
    day_offset, hour = SLOT_OFFSETS_DAYS.get(slot_key, (3, 10))
    start_dt = datetime.utcnow().replace(hour=hour, minute=0, second=0, microsecond=0) + timedelta(days=day_offset)
    end_dt = start_dt + timedelta(hours=1)

    payload = {
        "WhoId": contact_id,
        "WhatId": account_id,
        "Subject": subject,
        "Description": description,
        "StartDateTime": start_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "EndDateTime": end_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "Type": "Service Appointment",
    }
    resp = requests.post(
        f"{API_BASE}/sobjects/Event",
        headers=SF_HEADERS,
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("id", "")


def create_case(contact_id: str, account_id: str, subject: str, description: str) -> str:
    """Creates a Salesforce Case linked to the contact/account. Returns the case ID."""
    payload = {
        "ContactId": contact_id,
        "AccountId": account_id,
        "Subject": subject,
        "Description": description,
        "Status": "New",
        "Origin": "Phone",
        "Priority": "Medium",
        "Type": "Service",
    }
    resp = requests.post(
        f"{API_BASE}/sobjects/Case",
        headers=SF_HEADERS,
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("id", "")


class ServiceSchedulingController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Apex Field Services",
            agent_name="Riley",
            agent_purpose=(
                "to help Apex Field Services customers schedule on-site service appointments "
                "and ensure the right technician is dispatched"
            ),
        )

        self.set_task(
            objective=(
                "A customer has called to schedule a service appointment. Verify their identity, "
                "understand the service need, capture a preferred time slot, and book the appointment "
                "in Salesforce."
            ),
            checklist=[
                guava.Say(
                    "Thanks for calling Apex Field Services. My name is Riley. "
                    "I can help you schedule a service appointment. Let me pull up your account."
                ),
                guava.Field(
                    key="caller_email",
                    field_type="text",
                    description="Ask for the email address on their account.",
                    required=True,
                ),
                guava.Field(
                    key="service_type",
                    field_type="multiple_choice",
                    description="Ask what type of service they need.",
                    choices=[
                        "installation",
                        "repair",
                        "maintenance inspection",
                        "equipment replacement",
                        "other",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="issue_description",
                    field_type="text",
                    description=(
                        "Ask them to briefly describe the issue or what they'd like done. "
                        "Capture enough detail for a technician to prepare."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="preferred_slot",
                    field_type="multiple_choice",
                    description=(
                        "Ask which time slot works best for them. "
                        "Present the options naturally."
                    ),
                    choices=[
                        "tomorrow morning",
                        "tomorrow afternoon",
                        "day after tomorrow morning",
                        "day after tomorrow afternoon",
                        "next monday morning",
                        "next monday afternoon",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="site_address",
                    field_type="text",
                    description=(
                        "Ask for the service site address if it may differ from their account address. "
                        "Confirm it back to them."
                    ),
                    required=False,
                ),
            ],
            on_complete=self.book_appointment,
        )

        self.accept_call()

    def book_appointment(self):
        email = self.get_field("caller_email") or ""
        service_type = self.get_field("service_type") or "service"
        description = self.get_field("issue_description") or ""
        slot = self.get_field("preferred_slot") or "tomorrow morning"
        address = self.get_field("site_address") or ""

        logging.info("Looking up contact by email: %s", email)
        try:
            contact = find_contact_by_email(email)
        except Exception as e:
            logging.error("Contact lookup failed: %s", e)
            contact = None

        if not contact:
            self.hangup(
                final_instructions=(
                    "Let the caller know you couldn't find an account with that email. "
                    "Offer to transfer them to a team member who can assist manually. "
                    "Apologize for the inconvenience."
                )
            )
            return

        contact_id = contact["Id"]
        account_id = contact.get("AccountId") or ""
        first_name = contact.get("FirstName") or "there"

        full_description = f"Service type: {service_type}\nIssue: {description}"
        if address:
            full_description += f"\nSite address: {address}"

        subject = f"{service_type.title()} Appointment"

        logging.info("Creating Event and Case for contact %s — slot: %s", contact_id, slot)
        event_id = ""
        case_id = ""
        try:
            event_id = create_event(contact_id, account_id, subject, full_description, slot)
            logging.info("Event created: %s", event_id)
        except Exception as e:
            logging.error("Failed to create Event: %s", e)

        try:
            case_id = create_case(contact_id, account_id, subject, full_description)
            logging.info("Case created: %s", case_id)
        except Exception as e:
            logging.error("Failed to create Case: %s", e)

        slot_friendly = slot.replace("-", " ")

        self.hangup(
            final_instructions=(
                f"Let {first_name} know their {service_type} appointment has been scheduled for "
                f"{slot_friendly}. "
                + (f"Their service case number is {case_id}. " if case_id else "")
                + "A technician will arrive during that window and they'll receive a confirmation "
                "via email. Thank them for calling Apex Field Services and wish them a great day."
            )
        )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=ServiceSchedulingController,
    )

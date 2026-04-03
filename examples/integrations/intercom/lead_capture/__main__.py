import guava
import os
import logging
import requests
from datetime import datetime

logging.basicConfig(level=logging.INFO)

INTERCOM_ACCESS_TOKEN = os.environ["INTERCOM_ACCESS_TOKEN"]

BASE_URL = "https://api.intercom.io"
HEADERS = {
    "Authorization": f"Bearer {INTERCOM_ACCESS_TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Intercom-Version": "2.10",
}


def upsert_lead(
    name: str,
    email: str,
    company: str,
    phone: str,
    interest: str,
    budget: str,
    timeline: str,
) -> str:
    """Creates or updates an Intercom lead (contact with role=lead). Returns the contact ID."""
    # Search first
    resp = requests.post(
        f"{BASE_URL}/contacts/search",
        headers=HEADERS,
        json={
            "query": {
                "operator": "AND",
                "value": [{"field": "email", "operator": "=", "value": email}],
            }
        },
        timeout=10,
    )
    resp.raise_for_status()
    existing = resp.json().get("data", [])

    custom_attrs = {
        "interest": interest,
        "budget_range": budget,
        "timeline": timeline,
        "lead_source": "inbound_call",
    }

    if existing:
        contact_id = existing[0]["id"]
        requests.put(
            f"{BASE_URL}/contacts/{contact_id}",
            headers=HEADERS,
            json={"name": name, "phone": phone, "custom_attributes": custom_attrs},
            timeout=10,
        ).raise_for_status()
        return contact_id

    resp = requests.post(
        f"{BASE_URL}/contacts",
        headers=HEADERS,
        json={
            "role": "lead",
            "email": email,
            "name": name,
            "phone": phone,
            "custom_attributes": custom_attrs,
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["id"]


def tag_contact(contact_id: str, tag_name: str) -> None:
    """Applies a tag to the contact."""
    # First ensure tag exists
    tag_resp = requests.post(
        f"{BASE_URL}/tags",
        headers=HEADERS,
        json={"name": tag_name},
        timeout=10,
    )
    tag_resp.raise_for_status()
    tag_id = tag_resp.json()["id"]

    requests.post(
        f"{BASE_URL}/contacts/{contact_id}/tags",
        headers=HEADERS,
        json={"id": tag_id},
        timeout=10,
    ).raise_for_status()


class LeadCaptureController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Stackline",
            agent_name="Casey",
            agent_purpose=(
                "to qualify inbound sales inquiries for Stackline and create a lead record "
                "in Intercom so the sales team can follow up"
            ),
        )

        self.set_task(
            objective=(
                "A prospect has called Stackline. Greet them, understand their interest, "
                "collect qualification details, and create a lead in Intercom."
            ),
            checklist=[
                guava.Say(
                    "Thanks for calling Stackline! I'm Casey. "
                    "I'd love to learn a bit about you and what brings you in."
                ),
                guava.Field(
                    key="caller_name",
                    field_type="text",
                    description="Ask for their full name.",
                    required=True,
                ),
                guava.Field(
                    key="caller_email",
                    field_type="text",
                    description="Ask for their business email address.",
                    required=True,
                ),
                guava.Field(
                    key="caller_phone",
                    field_type="text",
                    description="Ask for the best phone number to reach them.",
                    required=False,
                ),
                guava.Field(
                    key="company",
                    field_type="text",
                    description="Ask what company they're with.",
                    required=True,
                ),
                guava.Field(
                    key="interest",
                    field_type="multiple_choice",
                    description="Ask what brings them to Stackline today.",
                    choices=[
                        "product demo",
                        "pricing information",
                        "technical evaluation",
                        "partnership",
                        "general inquiry",
                    ],
                    required=True,
                ),
                guava.Field(
                    key="budget",
                    field_type="multiple_choice",
                    description=(
                        "Ask if they have a budget range in mind. "
                        "Frame it naturally: 'Just to help connect you with the right team, "
                        "do you have a rough budget in mind?'"
                    ),
                    choices=["under $5k", "$5k–$20k", "$20k–$100k", "over $100k", "not sure yet"],
                    required=False,
                ),
                guava.Field(
                    key="timeline",
                    field_type="multiple_choice",
                    description="Ask when they're hoping to get started.",
                    choices=["immediately", "1–3 months", "3–6 months", "just exploring"],
                    required=False,
                ),
            ],
            on_complete=self.create_lead,
        )

        self.accept_call()

    def create_lead(self):
        name = self.get_field("caller_name") or "Unknown"
        email = self.get_field("caller_email") or ""
        phone = self.get_field("caller_phone") or ""
        company = self.get_field("company") or ""
        interest = self.get_field("interest") or "general inquiry"
        budget = self.get_field("budget") or "not sure yet"
        timeline = self.get_field("timeline") or "just exploring"

        logging.info("Creating Intercom lead for %s (%s) — interest: %s", name, email, interest)

        contact_id = ""
        try:
            contact_id = upsert_lead(name, email, company, phone, interest, budget, timeline)
            logging.info("Intercom lead created/updated: %s", contact_id)
        except Exception as e:
            logging.error("Failed to upsert Intercom lead: %s", e)

        if contact_id:
            try:
                tag_contact(contact_id, "inbound-call-lead")
                if interest == "product demo":
                    tag_contact(contact_id, "demo-requested")
                logging.info("Tags applied to contact %s.", contact_id)
            except Exception as e:
                logging.warning("Could not apply tags to contact %s: %s", contact_id, e)

        self.hangup(
            final_instructions=(
                f"Thank {name} for calling Stackline. Let them know their information has been "
                "passed to the sales team who will reach out within one business day. "
                + ("Mention that we'll schedule a demo as requested. " if interest == "product demo" else "")
                + "Wish them a great day."
            )
        )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=LeadCaptureController,
    )

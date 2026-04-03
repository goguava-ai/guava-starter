import guava
import os
import logging
import requests

logging.basicConfig(level=logging.INFO)

HUBSPOT_ACCESS_TOKEN = os.environ["HUBSPOT_ACCESS_TOKEN"]
HEADERS = {
    "Authorization": f"Bearer {HUBSPOT_ACCESS_TOKEN}",
    "Content-Type": "application/json",
}
BASE_URL = "https://api.hubapi.com"


def upsert_contact(email: str, firstname: str, lastname: str, company: str) -> str:
    """Creates or updates a HubSpot contact by email. Returns the contact ID."""
    payload = {
        "inputs": [
            {
                "idProperty": "email",
                "id": email,
                "properties": {
                    "email": email,
                    "firstname": firstname,
                    "lastname": lastname,
                    "company": company,
                    "lifecyclestage": "lead",
                },
            }
        ]
    }
    resp = requests.post(
        f"{BASE_URL}/crm/objects/2026-03/contacts/batch/upsert",
        headers=HEADERS,
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["results"][0]["id"]


def create_deal(contact_id: str, dealname: str) -> str:
    """Creates a new deal associated with the given contact. Returns the deal ID."""
    payload = {
        "properties": {
            "dealname": dealname,
            "dealstage": "appointmentscheduled",
            "pipeline": "default",
        },
        "associations": [
            {
                "to": {"id": contact_id},
                "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 3}],
            }
        ],
    }
    resp = requests.post(
        f"{BASE_URL}/crm/objects/2026-03/deals",
        headers=HEADERS,
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["id"]


class LeadCaptureController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Apex Solutions",
            agent_name="Riley",
            agent_purpose="to help new prospects connect with the Apex Solutions sales team",
        )

        self.set_task(
            objective=(
                "A potential new customer has called Apex Solutions. Greet them, collect their "
                "contact information and understand their interest so we can route them to the "
                "right sales representative and open an opportunity in our CRM."
            ),
            checklist=[
                guava.Say(
                    "Thanks for calling Apex Solutions. My name is Riley. "
                    "I'd love to learn a bit about what brought you to us today "
                    "and make sure we get you connected with the right team."
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
                    description="Ask for their business email address.",
                    required=True,
                ),
                guava.Field(
                    key="company_name",
                    field_type="text",
                    description="Ask what company they're calling from.",
                    required=True,
                ),
                guava.Field(
                    key="interest",
                    field_type="multiple_choice",
                    description=(
                        "Ask what brings them to Apex Solutions today. "
                        "Map their answer to the closest option."
                    ),
                    choices=["product demo", "pricing info", "general inquiry", "partnership"],
                    required=True,
                ),
                guava.Field(
                    key="budget_range",
                    field_type="multiple_choice",
                    description=(
                        "Ask if they have a rough budget in mind. "
                        "Frame it naturally: 'Just to help us match you with the right package, "
                        "do you have a rough budget range in mind?'"
                    ),
                    choices=["under $5k", "$5k–$25k", "$25k–$100k", "over $100k", "not sure yet"],
                    required=False,
                ),
                guava.Field(
                    key="timeline",
                    field_type="multiple_choice",
                    description="Ask when they're looking to get started.",
                    choices=["immediately", "1–3 months", "3–6 months", "just exploring"],
                    required=False,
                ),
            ],
            on_complete=self.create_crm_record,
        )

        self.accept_call()

    def create_crm_record(self):
        name = self.get_field("caller_name") or "Unknown"
        email = self.get_field("caller_email") or ""
        company = self.get_field("company_name") or ""
        interest = self.get_field("interest") or "general inquiry"

        parts = name.strip().split(" ", 1)
        firstname = parts[0]
        lastname = parts[1] if len(parts) > 1 else ""
        dealname = f"{company} — {interest.title()}" if company else f"{name} — {interest.title()}"

        logging.info("Upserting HubSpot contact for %s (%s)", name, email)
        try:
            contact_id = upsert_contact(email, firstname, lastname, company)
            deal_id = create_deal(contact_id, dealname)
            logging.info("Created HubSpot contact %s and deal %s", contact_id, deal_id)
            self.hangup(
                final_instructions=(
                    f"Thank {name} warmly for calling. Let them know their inquiry has been "
                    "recorded and a member of our sales team will reach out within one business day. "
                    "If they requested a demo, confirm it's been noted. Wish them a great day."
                )
            )
        except Exception as e:
            logging.error("Failed to create HubSpot records: %s", e)
            self.hangup(
                final_instructions=(
                    f"Apologize to {name} for a brief technical issue. Let them know their "
                    "information has been noted manually and a sales representative will reach "
                    "out within one business day. Thank them for their patience."
                )
            )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=LeadCaptureController,
    )

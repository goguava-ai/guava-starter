import guava
import os
import logging
from guava import logging_utils
import requests


HUBSPOT_ACCESS_TOKEN = os.environ["HUBSPOT_ACCESS_TOKEN"]
HEADERS = {
    "Authorization": f"Bearer {HUBSPOT_ACCESS_TOKEN}",
    "Content-Type": "application/json",
}
BASE_URL = "https://api.hubapi.com"

CONTACT_PROPERTIES = [
    "firstname",
    "lastname",
    "email",
    "phone",
    "company",
    "jobtitle",
    "lifecyclestage",
    "hs_lead_status",
]


def search_contact_by_email(email: str) -> dict | None:
    """Searches HubSpot for a contact by email. Returns the contact dict or None."""
    payload = {
        "filterGroups": [
            {"filters": [{"propertyName": "email", "operator": "EQ", "value": email}]}
        ],
        "properties": CONTACT_PROPERTIES,
        "limit": 1,
    }
    resp = requests.post(
        f"{BASE_URL}/crm/objects/2026-03/contacts/search",
        headers=HEADERS,
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()
    results = resp.json().get("results", [])
    return results[0] if results else None


class ContactLookupController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Apex Solutions",
            agent_name="Riley",
            agent_purpose=(
                "to help existing Apex Solutions customers look up their account details "
                "and answer questions about their contact record"
            ),
        )

        self.set_task(
            objective=(
                "An existing customer has called. Collect their email address, look up their "
                "account in our CRM, and answer any questions they have about their record — "
                "such as their lifecycle stage, assigned rep, or account status."
            ),
            checklist=[
                guava.Say(
                    "Thanks for calling Apex Solutions. I'm Riley, and I can help you look up "
                    "your account details. I'll just need to verify your identity first."
                ),
                guava.Field(
                    key="caller_email",
                    field_type="text",
                    description="Ask for their email address on file with Apex Solutions.",
                    required=True,
                ),
            ],
            on_complete=self.lookup_and_assist,
        )

        self.accept_call()

    def lookup_and_assist(self):
        email = self.get_field("caller_email") or ""
        logging.info("Looking up HubSpot contact for email: %s", email)

        try:
            contact = search_contact_by_email(email)
        except Exception as e:
            logging.error("HubSpot search failed for %s: %s", email, e)
            contact = None

        if not contact:
            self.hangup(
                final_instructions=(
                    "Let the caller know you were unable to find an account associated with "
                    "the email they provided. Ask them to double-check their email or offer to "
                    "transfer them to a live agent who can assist further. Be polite and apologetic."
                )
            )
            return

        props = contact.get("properties", {})
        firstname = props.get("firstname") or "there"
        company = props.get("company") or "your company"
        lifecycle = props.get("lifecyclestage") or "unknown"
        jobtitle = props.get("jobtitle") or ""
        phone = props.get("phone") or "not on file"

        context_lines = [
            f"You found an account for {firstname}.",
            f"Company: {company}.",
            f"Lifecycle stage: {lifecycle}.",
        ]
        if jobtitle:
            context_lines.append(f"Job title: {jobtitle}.")
        context_lines.append(f"Phone on file: {phone}.")

        logging.info(
            "Contact found: %s (stage: %s, company: %s)", firstname, lifecycle, company
        )

        self.hangup(
            final_instructions=(
                f"Greet {firstname} by name. "
                + " ".join(context_lines)
                + " Answer any questions they have about their account details using this information. "
                "If they ask about something not listed here, let them know you'll transfer them "
                "to their account representative for that level of detail. Be friendly and helpful."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=ContactLookupController,
    )

import guava
import os
import logging
from guava import logging_utils
import requests


SALESFORCE_INSTANCE_URL = os.environ["SALESFORCE_INSTANCE_URL"]
SALESFORCE_ACCESS_TOKEN = os.environ["SALESFORCE_ACCESS_TOKEN"]
SF_HEADERS = {
    "Authorization": f"Bearer {SALESFORCE_ACCESS_TOKEN}",
    "Content-Type": "application/json",
}
API_BASE = f"{SALESFORCE_INSTANCE_URL}/services/data/v66.0"


def find_contact_by_email(email: str) -> dict | None:
    """Searches for a Salesforce Contact by email. Returns the contact or None."""
    q = f"SELECT Id, FirstName, LastName, Phone, Title, Account.Name FROM Contact WHERE Email = '{email}' LIMIT 1"
    resp = requests.get(
        f"{API_BASE}/query",
        headers=SF_HEADERS,
        params={"q": q},
        timeout=10,
    )
    resp.raise_for_status()
    records = resp.json().get("records", [])
    return records[0] if records else None


def update_contact(contact_id: str, updates: dict) -> None:
    """Patches the given Contact record with the provided fields."""
    resp = requests.patch(
        f"{API_BASE}/sobjects/Contact/{contact_id}",
        headers=SF_HEADERS,
        json=updates,
        timeout=10,
    )
    resp.raise_for_status()


class ContactUpdateController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Meridian Consulting",
            agent_name="Casey",
            agent_purpose="to help customers update their contact information on file with Meridian Consulting",
        )

        self.set_task(
            objective=(
                "A customer has called to update their contact details. Verify their identity "
                "using their email address, find out what they'd like to change, and update "
                "their Salesforce Contact record accordingly."
            ),
            checklist=[
                guava.Say(
                    "Thanks for calling Meridian Consulting. I'm Casey, and I can help you "
                    "update your contact information on file. Let me pull up your account."
                ),
                guava.Field(
                    key="email",
                    field_type="text",
                    description="Ask for the email address they have on file with us.",
                    required=True,
                ),
                guava.Field(
                    key="update_field",
                    field_type="multiple_choice",
                    description="Ask what they'd like to update.",
                    choices=["phone number", "job title", "mailing address", "email address"],
                    required=True,
                ),
                guava.Field(
                    key="new_value",
                    field_type="text",
                    description=(
                        "Ask for the new value for the field they want to update. "
                        "Repeat it back to confirm accuracy."
                    ),
                    required=True,
                ),
            ],
            on_complete=self.apply_update,
        )

        self.accept_call()

    def apply_update(self):
        email = self.get_field("email") or ""
        update_field = self.get_field("update_field") or ""
        new_value = self.get_field("new_value") or ""

        logging.info("Looking up contact by email: %s", email)
        try:
            contact = find_contact_by_email(email)
        except Exception as e:
            logging.error("Contact lookup failed: %s", e)
            contact = None

        if not contact:
            self.hangup(
                final_instructions=(
                    "Let the caller know you were unable to find an account with that email address. "
                    "Ask them to double-check the email or offer to transfer them to a team member. "
                    "Be apologetic and helpful."
                )
            )
            return

        contact_id = contact["Id"]
        first_name = contact.get("FirstName") or "there"

        field_map = {
            "phone number": "Phone",
            "job title": "Title",
            "mailing address": "MailingStreet",
            "email address": "Email",
        }
        sf_field = field_map.get(update_field)

        if not sf_field:
            self.hangup(
                final_instructions=(
                    f"Apologize to {first_name} and let them know you're unable to update "
                    f"'{update_field}' over the phone. Ask them to contact support via email "
                    "for assistance with that change."
                )
            )
            return

        logging.info("Updating Contact %s — %s → %s", contact_id, sf_field, new_value)
        try:
            update_contact(contact_id, {sf_field: new_value})
            logging.info("Contact %s updated successfully.", contact_id)
            self.hangup(
                final_instructions=(
                    f"Let {first_name} know their {update_field} has been updated successfully. "
                    "Confirm the new value back to them. Thank them for calling Meridian Consulting "
                    "and wish them a great day."
                )
            )
        except Exception as e:
            logging.error("Failed to update Contact %s: %s", contact_id, e)
            self.hangup(
                final_instructions=(
                    f"Apologize to {first_name} for a brief technical issue and let them know "
                    "the update could not be saved right now. Ask them to try again shortly or "
                    "email support@meridianconsulting.com with the change. Thank them for their patience."
                )
            )


if __name__ == "__main__":
    logging_utils.configure_logging()
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=ContactUpdateController,
    )

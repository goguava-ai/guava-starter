import guava
import os
import logging
from guava import logging_utils
import requests


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


def find_contact_by_email(email: str) -> dict | None:
    """Searches Dynamics 365 for a contact by email address. Returns the contact object or None."""
    resp = requests.get(
        f"{API_BASE}/contacts",
        headers=GET_HEADERS,
        params={
            "$filter": f"emailaddress1 eq '{email}'",
            "$select": "contactid,fullname,emailaddress1,telephone1,jobtitle,accountid",
        },
        timeout=10,
    )
    resp.raise_for_status()
    results = resp.json().get("value", [])
    return results[0] if results else None


def update_contact(contact_id: str, fields: dict) -> None:
    """Applies a partial update to a contact record via PATCH."""
    resp = requests.patch(
        f"{API_BASE}/contacts({contact_id})",
        headers=HEADERS,
        json=fields,
        timeout=10,
    )
    resp.raise_for_status()


class ContactUpdateController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Pinnacle Solutions",
            agent_name="Alex",
            agent_purpose="to help customers update their contact information in the Pinnacle Solutions system",
        )

        self.set_task(
            objective=(
                "A customer has called to update their contact details on file. Look up their "
                "account by their current email address, ask what they would like to update, "
                "collect the new values, and apply the changes."
            ),
            checklist=[
                guava.Say(
                    "Thank you for calling Pinnacle Solutions. My name is Alex. "
                    "I can help you update your contact information on file."
                ),
                guava.Field(
                    key="current_email",
                    field_type="text",
                    description=(
                        "Ask for the email address currently on their account so we can locate "
                        "their record."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="field_to_update",
                    field_type="multiple_choice",
                    description=(
                        "Ask which piece of contact information they would like to update. "
                        "If they want to update several fields, select 'all'."
                    ),
                    choices=["phone", "email", "job-title", "address", "all"],
                    required=True,
                ),
                guava.Field(
                    key="new_phone",
                    field_type="text",
                    description=(
                        "If they are updating their phone number (or selected 'all'), "
                        "ask for their new phone number. Otherwise skip."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="new_email",
                    field_type="text",
                    description=(
                        "If they are updating their email address (or selected 'all'), "
                        "ask for their new email address. Otherwise skip."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="new_job_title",
                    field_type="text",
                    description=(
                        "If they are updating their job title (or selected 'all'), "
                        "ask for their new job title. Otherwise skip."
                    ),
                    required=False,
                ),
            ],
            on_complete=self.apply_update,
        )

        self.accept_call()

    def apply_update(self):
        current_email = (self.get_field("current_email") or "").strip()
        field_to_update = self.get_field("field_to_update") or ""
        new_phone = (self.get_field("new_phone") or "").strip()
        new_email = (self.get_field("new_email") or "").strip()
        new_job_title = (self.get_field("new_job_title") or "").strip()

        logging.info(
            "Contact update request — lookup email: %s, field: %s", current_email, field_to_update
        )

        try:
            contact = find_contact_by_email(current_email)
            if not contact:
                self.hangup(
                    final_instructions=(
                        "Let the caller know we were unable to find an account with that email "
                        "address. Ask them to double-check the address and call back, or suggest "
                        "they contact support@pinnaclesolutions.com directly. "
                        "Thank them for calling Pinnacle Solutions."
                    )
                )
                return

            contact_id = contact["contactid"]
            contact_name = contact.get("fullname", "the caller")

            # Build the update payload based on what was collected
            update_payload: dict = {}
            updated_fields: list[str] = []

            if new_phone:
                update_payload["telephone1"] = new_phone
                updated_fields.append("phone number")

            if new_email:
                update_payload["emailaddress1"] = new_email
                updated_fields.append("email address")

            if new_job_title:
                update_payload["jobtitle"] = new_job_title
                updated_fields.append("job title")

            if not update_payload:
                self.hangup(
                    final_instructions=(
                        f"Let {contact_name} know we were not able to apply any changes because no "
                        "new values were provided. Ask them to call back when they have the updated "
                        "information ready. Thank them for calling Pinnacle Solutions."
                    )
                )
                return

            logging.info(
                "Applying update to contact %s — fields: %s", contact_id, updated_fields
            )
            update_contact(contact_id, update_payload)
            logging.info("Contact %s updated successfully", contact_id)

            fields_summary = ", ".join(updated_fields)
            self.hangup(
                final_instructions=(
                    f"Let {contact_name} know their {fields_summary} "
                    f"{'has' if len(updated_fields) == 1 else 'have'} been updated successfully "
                    "in our system. Let them know the changes are effective immediately. "
                    "Thank them for calling Pinnacle Solutions and wish them a great day."
                )
            )

        except Exception as e:
            logging.error("Failed to update contact for %s: %s", current_email, e)
            self.hangup(
                final_instructions=(
                    "Apologize for a technical issue and let the caller know they can also "
                    "update their information through the Pinnacle Solutions customer portal "
                    "or by emailing support@pinnaclesolutions.com. "
                    "Thank them for their patience."
                )
            )


if __name__ == "__main__":
    logging_utils.configure_logging()
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=ContactUpdateController,
    )

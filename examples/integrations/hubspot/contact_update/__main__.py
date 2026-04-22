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

_NO_CHANGE = {"no change", "n/a", "none", "same", "no", ""}


def search_contact_by_email(email: str) -> dict | None:
    """Returns the first matching HubSpot contact for the given email, or None."""
    payload = {
        "filterGroups": [
            {"filters": [{"propertyName": "email", "operator": "EQ", "value": email}]}
        ],
        "properties": ["firstname", "lastname", "email", "phone", "company", "jobtitle"],
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


def update_contact(contact_id: str, updates: dict) -> None:
    resp = requests.patch(
        f"{BASE_URL}/crm/objects/2026-03/contacts/{contact_id}",
        headers=HEADERS,
        json={"properties": updates},
        timeout=10,
    )
    resp.raise_for_status()


agent = guava.Agent(
    name="Riley",
    organization="Apex Solutions",
    purpose=(
        "to help existing Apex Solutions customers update their contact information "
        "in our records"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "apply_updates",
        objective=(
            "An existing customer has called to update their contact information. "
            "Verify their identity by looking up their email, then collect the "
            "new details they want to change and apply the updates."
        ),
        checklist=[
            guava.Say(
                "Thanks for calling Apex Solutions. I'm Riley. "
                "I can help you update your contact information on file. "
                "Let me pull up your account first."
            ),
            guava.Field(
                key="caller_email",
                field_type="text",
                description="Ask for their current email address on file.",
                required=True,
            ),
            guava.Field(
                key="new_phone",
                field_type="text",
                description=(
                    "Ask if they would like to update their phone number. "
                    "Capture the new number, or 'no change' if they don't want to update it."
                ),
                required=False,
            ),
            guava.Field(
                key="new_job_title",
                field_type="text",
                description=(
                    "Ask if their job title has changed. "
                    "Capture the new title or 'no change'."
                ),
                required=False,
            ),
            guava.Field(
                key="new_company",
                field_type="text",
                description=(
                    "Ask if they've moved to a different company. "
                    "Capture the new company name or 'no change'."
                ),
                required=False,
            ),
            guava.Field(
                key="new_email",
                field_type="text",
                description=(
                    "Ask if they need to update their email address. "
                    "Capture the new email or 'no change'."
                ),
                required=False,
            ),
        ],
    )


@agent.on_task_complete("apply_updates")
def on_done(call: guava.Call) -> None:
    email = call.get_field("caller_email") or ""

    logging.info("Looking up HubSpot contact for email: %s", email)
    try:
        contact = search_contact_by_email(email)
    except Exception as e:
        logging.error("HubSpot search failed for %s: %s", email, e)
        contact = None

    if not contact:
        call.hangup(
            final_instructions=(
                "Let the caller know you couldn't find an account associated with that email. "
                "Ask them to verify their email or offer to transfer them to a live agent. "
                "Be apologetic and helpful."
            )
        )
        return

    contact_id = contact["id"]
    firstname = contact.get("properties", {}).get("firstname") or "there"

    raw = {
        "phone": call.get_field("new_phone") or "",
        "jobtitle": call.get_field("new_job_title") or "",
        "company": call.get_field("new_company") or "",
        "email": call.get_field("new_email") or "",
    }
    updates = {k: v.strip() for k, v in raw.items() if v.strip().lower() not in _NO_CHANGE}

    if not updates:
        call.hangup(
            final_instructions=(
                f"Let {firstname} know that no changes were made since no updates were requested. "
                "Thank them for calling."
            )
        )
        return

    logging.info("Updating HubSpot contact %s: %s", contact_id, list(updates.keys()))
    try:
        update_contact(contact_id, updates)
        updated_fields = ", ".join(k.replace("jobtitle", "job title") for k in updates)
        logging.info("Contact %s updated successfully", contact_id)
        call.hangup(
            final_instructions=(
                f"Let {firstname} know their contact information has been updated successfully. "
                f"Confirm which fields were changed: {updated_fields}. "
                "Ask if there's anything else we can help with and thank them for calling."
            )
        )
    except Exception as e:
        logging.error("Failed to update contact %s: %s", contact_id, e)
        call.hangup(
            final_instructions=(
                f"Apologize to {firstname} for a technical issue and let them know their "
                "update request has been noted — our team will apply the changes manually "
                "within one business day. Thank them for their patience."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])

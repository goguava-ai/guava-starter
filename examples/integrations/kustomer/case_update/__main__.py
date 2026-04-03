import guava
import os
import logging
import requests
from urllib.parse import quote

logging.basicConfig(level=logging.INFO)

TOKEN = os.environ["KUSTOMER_API_TOKEN"]
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
BASE_URL = "https://api.kustomerapp.com/v1"


def get_customer_by_email(email: str) -> dict | None:
    """Looks up a Kustomer customer by email address. Returns the customer object or None."""
    resp = requests.get(
        f"{BASE_URL}/customers/email/{quote(email, safe='')}",
        headers=HEADERS,
        timeout=10,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    data = resp.json().get("data")
    return data if data else None


def get_conversation(conversation_id: str) -> dict | None:
    """Fetches a single conversation by ID. Returns the conversation object or None."""
    resp = requests.get(
        f"{BASE_URL}/conversations/{conversation_id}",
        headers=HEADERS,
        timeout=10,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    data = resp.json().get("data")
    return data if data else None


def post_message(conversation_id: str, body: str) -> dict:
    """Posts an inbound voice message to an existing conversation. Returns the message object."""
    payload = {
        "body": body,
        "direction": "in",
        "channel": "voice",
    }
    resp = requests.post(
        f"{BASE_URL}/conversations/{conversation_id}/messages",
        headers=HEADERS,
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["data"]


class CaseUpdateController(guava.CallController):
    def __init__(self):
        super().__init__()
        self.conversation = None

        self.set_persona(
            organization_name="Brightpath Support",
            agent_name="Alex",
            agent_purpose="to help customers add information to an existing open support case with Brightpath Support",
        )

        self.set_task(
            objective=(
                "A customer has called to add information to an existing open support case. "
                "Collect their email address, case ID, and the update they want to add, "
                "then record it on the case."
            ),
            checklist=[
                guava.Say(
                    "Thank you for calling Brightpath Support. My name is Alex. "
                    "I can add new information to an existing open support case for you."
                ),
                guava.Field(
                    key="caller_email",
                    field_type="text",
                    description="Ask for the email address associated with their support account.",
                    required=True,
                ),
                guava.Field(
                    key="case_id",
                    field_type="text",
                    description=(
                        "Ask for the case ID they'd like to update. This is the conversation ID "
                        "provided when their case was opened."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="update_details",
                    field_type="text",
                    description=(
                        "Ask what new information they'd like to add to their case — "
                        "any additional symptoms, steps they've tried, error messages, or other "
                        "relevant details. Capture their full message."
                    ),
                    required=True,
                ),
            ],
            on_complete=self.post_update,
        )

        self.accept_call()

    def post_update(self):
        email = (self.get_field("caller_email") or "").strip()
        case_id = (self.get_field("case_id") or "").strip()
        update_details = self.get_field("update_details") or ""

        if not case_id:
            self.hangup(
                final_instructions=(
                    "Let the caller know the case ID they provided doesn't appear to be valid. "
                    "Ask them to check their case confirmation email for the correct ID and call "
                    "back. Thank them for calling Brightpath Support."
                )
            )
            return

        logging.info("Looking up conversation %s for update from %s", case_id, email)

        # Verify the customer exists
        try:
            customer = get_customer_by_email(email)
        except Exception as e:
            logging.error("Failed to look up customer by email %s: %s", email, e)
            customer = None

        if not customer:
            self.hangup(
                final_instructions=(
                    "Let the caller know we were unable to find an account matching that email "
                    "address. Ask them to double-check and call back, or offer to connect them "
                    "with a live agent. Thank them for calling Brightpath Support."
                )
            )
            return

        # Verify the conversation exists
        try:
            self.conversation = get_conversation(case_id)
        except Exception as e:
            logging.error("Failed to fetch conversation %s: %s", case_id, e)
            self.conversation = None

        if not self.conversation:
            self.hangup(
                final_instructions=(
                    f"Let the caller know we could not find a case with ID {case_id}. "
                    "Ask them to double-check the ID from their confirmation email. "
                    "Thank them for calling Brightpath Support."
                )
            )
            return

        conv_attrs = self.conversation.get("attributes", {})
        status = conv_attrs.get("status", "open")

        if status in ("done", "snoozed"):
            self.hangup(
                final_instructions=(
                    f"Let the caller know that case {case_id} is currently marked as {status} "
                    "and may no longer be active. If the issue has recurred, suggest they call "
                    "back to open a new case. Thank them for calling Brightpath Support."
                )
            )
            return

        # Post the update as a new inbound message
        customer_name = customer.get("attributes", {}).get("name") or "the caller"
        message_body = f"Phone update from {customer_name}:\n\n{update_details}"

        logging.info("Posting update message to conversation %s", case_id)
        try:
            post_message(conversation_id=case_id, body=message_body)
            logging.info("Update posted to conversation %s", case_id)

            self.hangup(
                final_instructions=(
                    f"Let {customer_name} know their update has been added to case {case_id}. "
                    "Our support team will review it and follow up by email. "
                    "Thank them for calling Brightpath Support."
                )
            )
        except Exception as e:
            logging.error("Failed to post update to conversation %s: %s", case_id, e)
            self.hangup(
                final_instructions=(
                    f"Apologize to {customer_name} for a technical issue and let them know they "
                    "can reply to their case confirmation email to add the update. "
                    "Thank them for their patience."
                )
            )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=CaseUpdateController,
    )

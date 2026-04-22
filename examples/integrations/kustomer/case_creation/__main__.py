import guava
import os
import logging
from guava import logging_utils
import requests
from urllib.parse import quote


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


def create_customer(name: str, email: str) -> dict:
    """Creates a new Kustomer customer record. Returns the created customer object."""
    payload = {
        "name": name,
        "emails": [{"email": email}],
    }
    resp = requests.post(f"{BASE_URL}/customers", headers=HEADERS, json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json()["data"]


def create_conversation(customer_id: str) -> dict:
    """Opens a new voice conversation for a customer. Returns the conversation object."""
    payload = {
        "customer": {"id": customer_id},
        "channel": "voice",
        "status": "open",
        "tags": ["guava", "voice"],
    }
    resp = requests.post(f"{BASE_URL}/conversations", headers=HEADERS, json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json()["data"]


def post_message(conversation_id: str, body: str) -> dict:
    """Posts an inbound voice message to a conversation. Returns the message object."""
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


class CaseCreationController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Brightpath Support",
            agent_name="Jordan",
            agent_purpose="to help customers report issues and open support cases with Brightpath Support",
        )

        self.set_task(
            objective=(
                "A customer has called Brightpath Support to report an issue. Greet them, collect "
                "their contact information and a clear description of their problem so we can open "
                "a support case."
            ),
            checklist=[
                guava.Say(
                    "Thank you for calling Brightpath Support. My name is Jordan. "
                    "I'm here to help you today. I'll collect some details and open a support "
                    "case for you right away."
                ),
                guava.Field(
                    key="caller_name",
                    field_type="text",
                    description="Ask the caller for their full name.",
                    required=True,
                ),
                guava.Field(
                    key="caller_email",
                    field_type="text",
                    description="Ask for their email address so we can link the case to their account and send updates.",
                    required=True,
                ),
                guava.Field(
                    key="issue_type",
                    field_type="multiple_choice",
                    description=(
                        "Ask what type of issue they're experiencing. "
                        "Map their answer to the closest category."
                    ),
                    choices=["billing", "technical", "account-access", "product-feedback", "other"],
                    required=True,
                ),
                guava.Field(
                    key="issue_summary",
                    field_type="text",
                    description=(
                        "Ask the caller to briefly describe the issue they're experiencing. "
                        "Capture a clear one-sentence summary."
                    ),
                    required=True,
                ),
                guava.Field(
                    key="severity",
                    field_type="multiple_choice",
                    description=(
                        "Ask how severely this issue is affecting them. "
                        "Map their answer to: low (minor inconvenience), medium (some impact), "
                        "high (significant impact), or critical (completely blocked)."
                    ),
                    choices=["low", "medium", "high", "critical"],
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
        severity = self.get_field("severity") or "medium"

        logging.info(
            "Opening case for %s (%s) — type: %s, severity: %s", name, email, issue_type, severity
        )

        try:
            # Look up or create the customer
            customer = get_customer_by_email(email)
            if customer:
                customer_id = customer["id"]
                logging.info("Found existing Kustomer customer: %s", customer_id)
            else:
                logging.info("No existing customer for %s — creating new record", email)
                customer = create_customer(name=name, email=email)
                customer_id = customer["id"]
                logging.info("Created Kustomer customer: %s", customer_id)

            # Open a conversation (case)
            conversation = create_conversation(customer_id=customer_id)
            conv_id = conversation["id"]
            logging.info("Created Kustomer conversation: %s", conv_id)

            # Post the issue details as the opening message
            message_body = (
                f"Issue type: {issue_type}\n"
                f"Severity: {severity}\n"
                f"Summary: {summary}"
            )
            post_message(conversation_id=conv_id, body=message_body)
            logging.info("Posted opening message to conversation %s", conv_id)

            self.hangup(
                final_instructions=(
                    f"Let {name} know their support case has been created successfully. "
                    f"Their case ID is {conv_id}. "
                    "Tell them our team will review their case and follow up by email based on "
                    "the severity they reported. "
                    "Thank them for calling Brightpath Support."
                )
            )

        except Exception as e:
            logging.error("Failed to create Kustomer case for %s: %s", email, e)
            self.hangup(
                final_instructions=(
                    f"Apologize to {name} for a technical issue and let them know a support "
                    "agent will follow up with them by email to manually open their case. "
                    "Thank them for their patience."
                )
            )


if __name__ == "__main__":
    logging_utils.configure_logging()
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=CaseCreationController,
    )

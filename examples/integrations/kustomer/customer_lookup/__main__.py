import logging
import os
from urllib.parse import quote

import guava
import requests
from guava import logging_utils

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


def get_customer_by_phone(phone: str) -> dict | None:
    """Looks up a Kustomer customer by phone number. Returns the customer object or None."""
    resp = requests.get(
        f"{BASE_URL}/customers/phone/{quote(phone, safe='')}",
        headers=HEADERS,
        timeout=10,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    data = resp.json().get("data")
    return data if data else None


def get_customer_conversations(customer_id: str) -> list[dict]:
    """Returns conversations for a customer, most recent first."""
    resp = requests.get(
        f"{BASE_URL}/customers/{customer_id}/conversations",
        headers=HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("data", [])


agent = guava.Agent(
    name="Sam",
    organization="Brightpath Support",
    purpose="to help callers look up their customer profile and recent case history with Brightpath Support",
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "lookup_customer",
        objective=(
            "A caller wants to look up their customer profile and recent case history. "
            "Ask how they'd like to look up their account, collect the lookup value, "
            "then retrieve and summarize their profile and recent cases."
        ),
        checklist=[
            guava.Say(
                "Thank you for calling Brightpath Support. My name is Sam. "
                "I can pull up your account and review your recent cases with you."
            ),
            guava.Field(
                key="lookup_method",
                field_type="multiple_choice",
                description=(
                    "Ask whether they'd like to look up their account by email address or by "
                    "phone number."
                ),
                choices=["email", "phone"],
                required=True,
            ),
            guava.Field(
                key="lookup_value",
                field_type="text",
                description=(
                    "Ask for their email address or phone number based on the method they chose. "
                    "Capture it exactly as they provide it."
                ),
                required=True,
            ),
        ],
    )


@agent.on_task_complete("lookup_customer")
def on_done(call: guava.Call) -> None:
    lookup_method = call.get_field("lookup_method") or "email"
    lookup_value = (call.get_field("lookup_value") or "").strip()

    logging.info("Looking up customer by %s: %s", lookup_method, lookup_value)

    customer = None
    try:
        if lookup_method == "phone":
            customer = get_customer_by_phone(lookup_value)
        else:
            customer = get_customer_by_email(lookup_value)
    except Exception as e:
        logging.error("Failed to look up customer by %s: %s", lookup_method, e)

    if not customer:
        call.hangup(
            final_instructions=(
                "Let the caller know we were unable to find an account matching the "
                f"{lookup_method} they provided. Ask them to double-check and try again, "
                "or offer to connect them with a live agent. Thank them for calling "
                "Brightpath Support."
            )
        )
        return

    customer_id = customer["id"]
    attrs = customer.get("attributes", {})
    customer_name = attrs.get("name") or "Valued Customer"
    created_at = attrs.get("createdAt", "")

    logging.info("Found customer %s (%s)", customer_name, customer_id)

    # Fetch conversation history
    try:
        conversations = get_customer_conversations(customer_id)
    except Exception as e:
        logging.error("Failed to fetch conversations for customer %s: %s", customer_id, e)
        conversations = []

    total_convs = len(conversations)
    most_recent_summary = ""
    if conversations:
        recent = conversations[0]
        recent_attrs = recent.get("attributes", {})
        recent_summary = (
            recent_attrs.get("preview")
            or recent_attrs.get("subject")
            or "an unspecified issue"
        )
        recent_status = recent_attrs.get("status", "unknown")
        most_recent_summary = f"Most recent case is about '{recent_summary}' and is currently {recent_status}."

    logging.info(
        "Customer %s has %d conversation(s)", customer_name, total_convs
    )

    # Build the summary for the agent to read back
    since_phrase = f" Their account was created on {created_at[:10]}." if created_at else ""
    conv_phrase = (
        f" They have {total_convs} past conversation{'s' if total_convs != 1 else ''} on record."
        if total_convs > 0
        else " They have no past conversations on record."
    )
    recent_phrase = f" {most_recent_summary}" if most_recent_summary else ""

    call.hangup(
        final_instructions=(
            f"Greet {customer_name} and let them know you found their account.{since_phrase}"
            f"{conv_phrase}{recent_phrase} "
            "Thank them for calling Brightpath Support."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])

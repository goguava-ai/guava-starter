import guava
import os
import logging
from guava import logging_utils
import requests
from datetime import datetime


FRONT_API_TOKEN = os.environ["FRONT_API_TOKEN"]

BASE_URL = "https://api2.frontapp.com"
HEADERS = {
    "Authorization": f"Bearer {FRONT_API_TOKEN}",
    "Content-Type": "application/json",
}


def search_contact(email: str) -> dict | None:
    """Searches Front for a contact by email handle. Returns the contact or None."""
    resp = requests.get(
        f"{BASE_URL}/contacts",
        headers=HEADERS,
        params={"q[handles][handle]": email, "q[handles][source]": "email"},
        timeout=10,
    )
    resp.raise_for_status()
    results = resp.json().get("_results", [])
    return results[0] if results else None


def get_contact_conversations(contact_id: str, limit: int = 3) -> list:
    """Returns the most recent conversations for a contact."""
    resp = requests.get(
        f"{BASE_URL}/contacts/{contact_id}/conversations",
        headers=HEADERS,
        params={"limit": limit, "sort_order": "desc"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("_results", [])


def format_date(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%B %d, %Y")
    except Exception:
        return iso[:10] if iso else "unknown"


agent = guava.Agent(
    name="Morgan",
    organization="Relay Agency",
    purpose=(
        "to provide warm, informed support to Relay Agency customers by looking up "
        "their Front contact record before assisting them"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "lookup_and_assist",
        objective=(
            "Look up the caller's Front contact profile and recent conversations "
            "so the agent can assist them with context."
        ),
        checklist=[
            guava.Say(
                "Thanks for calling Relay Agency. I'm Morgan. "
                "Let me pull up your record — what's the email address on your account?"
            ),
            guava.Field(
                key="caller_email",
                field_type="text",
                description="Ask for the caller's email address.",
                required=True,
            ),
        ],
    )


@agent.on_task_complete("lookup_and_assist")
def on_done(call: guava.Call) -> None:
    email = (call.get_field("caller_email") or "").strip()

    logging.info("Looking up Front contact for email: %s", email)
    contact = None
    try:
        contact = search_contact(email)
    except Exception as e:
        logging.error("Front contact lookup failed: %s", e)

    if not contact:
        call.hangup(
            final_instructions=(
                "Let the caller know you couldn't find an account with that email. "
                "Offer to assist them anyway or check if they used a different email. "
                "Be warm and helpful."
            )
        )
        return

    contact_id = contact.get("id", "")
    name = contact.get("name") or "there"
    description = contact.get("description") or ""
    groups = [g.get("name", "") for g in (contact.get("groups") or {}).get("_results", [])]

    conversations = []
    if contact_id:
        try:
            convs = get_contact_conversations(contact_id, limit=3)
            for c in convs:
                subj = c.get("subject") or "(no subject)"
                status = c.get("status") or "unknown"
                conversations.append(f"'{subj}' ({status})")
        except Exception as e:
            logging.error("Failed to fetch conversations for contact %s: %s", contact_id, e)

    context = [f"Contact: {name} ({email})"]
    if description:
        context.append(f"Notes: {description}")
    if groups:
        context.append(f"Groups: {', '.join(groups)}")
    if conversations:
        context.append(f"Recent conversations: {'; '.join(conversations)}")
    else:
        context.append("No recent conversations found.")

    logging.info("Front contact found: %s", "; ".join(context))

    call.hangup(
        final_instructions=(
            f"Greet {name} by name and ask how you can help today. "
            "Use the following context naturally — don't read it aloud: "
            f"{'; '.join(context)}. "
            "If there are recent open or archived conversations, reference them naturally "
            "if it helps the caller. Thank them for calling Relay Agency when done."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])

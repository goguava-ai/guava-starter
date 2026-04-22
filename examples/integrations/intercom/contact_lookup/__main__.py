import guava
import os
import logging
from guava import logging_utils
import requests
from datetime import datetime


INTERCOM_ACCESS_TOKEN = os.environ["INTERCOM_ACCESS_TOKEN"]

BASE_URL = "https://api.intercom.io"
HEADERS = {
    "Authorization": f"Bearer {INTERCOM_ACCESS_TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Intercom-Version": "2.10",
}


def find_contact_by_email(email: str) -> dict | None:
    """Searches Intercom for a contact by email. Returns the contact or None."""
    resp = requests.post(
        f"{BASE_URL}/contacts/search",
        headers=HEADERS,
        json={
            "query": {
                "operator": "AND",
                "value": [
                    {"field": "email", "operator": "=", "value": email}
                ],
            }
        },
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json().get("data", [])
    return data[0] if data else None


def format_last_seen(ts: int | None) -> str:
    if not ts:
        return "never"
    return datetime.utcfromtimestamp(ts).strftime("%B %d, %Y")


agent = guava.Agent(
    name="Casey",
    organization="Stackline",
    purpose=(
        "to provide fast, context-aware support to Stackline customers by looking up "
        "their Intercom profile before the conversation begins"
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
            "Look up the caller's Intercom profile by email so the agent can provide "
            "personalized, informed support without asking for background they've already shared."
        ),
        checklist=[
            guava.Say(
                "Thanks for calling Stackline Support. I'm Casey. "
                "Let me pull up your account — what's the email address on your account?"
            ),
            guava.Field(
                key="caller_email",
                field_type="text",
                description="Ask for their email address.",
                required=True,
            ),
        ],
    )


@agent.on_task_complete("lookup_and_assist")
def on_done(call: guava.Call) -> None:
    email = (call.get_field("caller_email") or "").strip()

    logging.info("Looking up Intercom contact for email: %s", email)
    contact = None
    try:
        contact = find_contact_by_email(email)
    except Exception as e:
        logging.error("Intercom contact lookup failed: %s", e)

    if not contact:
        call.hangup(
            final_instructions=(
                "Let the caller know you couldn't find an account with that email. "
                "Suggest they may have used a different email or offer to proceed without an account verification. "
                "Be helpful and not dismissive."
            )
        )
        return

    name = contact.get("name") or "there"
    plan = (contact.get("custom_attributes") or {}).get("plan") or ""
    last_seen_ts = contact.get("last_seen_at")
    last_seen = format_last_seen(last_seen_ts)
    session_count = contact.get("session_count") or 0
    created_ts = contact.get("created_at")
    member_since = format_last_seen(created_ts)
    unread_count = contact.get("unread_conversations_count") or 0

    context_parts = [f"Customer: {name} ({email})"]
    if plan:
        context_parts.append(f"Plan: {plan}")
    context_parts.append(f"Member since: {member_since}")
    context_parts.append(f"Last active: {last_seen}")
    context_parts.append(f"Total sessions: {session_count}")
    if unread_count:
        context_parts.append(f"Unread conversations: {unread_count}")

    logging.info("Intercom contact found: %s — %s", name, "; ".join(context_parts))

    call.hangup(
        final_instructions=(
            f"Greet {name} by name warmly. Use the following context to personalize "
            "your support — do not read it out loud robotically, just use it naturally: "
            f"{'; '.join(context_parts)}. "
            "Ask how you can help them today and provide excellent, informed support. "
            + (f"Note they have {unread_count} unread conversation(s) — mention this if relevant. "
               if unread_count else "")
            + "Thank them for calling Stackline when done."
        )
    )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])

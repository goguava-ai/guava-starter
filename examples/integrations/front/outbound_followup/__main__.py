import guava
import os
import logging
from guava import logging_utils
import argparse
import requests
from datetime import datetime, timezone


FRONT_API_TOKEN = os.environ["FRONT_API_TOKEN"]

BASE_URL = "https://api2.frontapp.com"
HEADERS = {
    "Authorization": f"Bearer {FRONT_API_TOKEN}",
    "Content-Type": "application/json",
}


def get_conversation(conversation_id: str) -> dict | None:
    resp = requests.get(
        f"{BASE_URL}/conversations/{conversation_id}",
        headers=HEADERS,
        timeout=10,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def add_comment(conversation_id: str, author_id: str, body: str) -> None:
    """Adds a teammate comment (internal note) to the conversation."""
    payload = {"author_id": author_id, "body": body}
    resp = requests.post(
        f"{BASE_URL}/conversations/{conversation_id}/comments",
        headers=HEADERS,
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()


def update_conversation_status(conversation_id: str, status: str) -> None:
    """Updates the conversation status (archived, open, spam, deleted)."""
    resp = requests.patch(
        f"{BASE_URL}/conversations/{conversation_id}",
        headers=HEADERS,
        json={"status": status},
        timeout=10,
    )
    resp.raise_for_status()


agent = guava.Agent(
    name="Morgan",
    organization="Relay Agency",
    purpose=(
        "to follow up personally with customers on pending Front conversations "
        "and resolve any outstanding questions"
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    conversation_id = call.get_variable("conversation_id")

    conv_subject = "your recent inquiry"
    try:
        conv = get_conversation(conversation_id)
        if conv and conv.get("subject"):
            conv_subject = f"'{conv['subject']}'"
    except Exception as e:
        logging.error("Failed to fetch conversation %s pre-call: %s", conversation_id, e)

    call.set_variable("conv_subject", conv_subject)

    call.reach_person(contact_full_name=contact_name)


@agent.on_reach_person
def on_reach_person(call: guava.Call, outcome: str) -> None:
    if outcome == "unavailable":
        contact_name = call.get_variable("contact_name")
        conversation_id = call.get_variable("conversation_id")
        author_id = call.get_variable("author_id")
        conv_subject = call.get_variable("conv_subject")

        logging.info("Unable to reach %s for follow-up on conversation %s.", contact_name, conversation_id)
        try:
            add_comment(
                conversation_id,
                author_id,
                f"Follow-up call attempted — {contact_name} unavailable, voicemail left. "
                f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            )
        except Exception as e:
            logging.error("Failed to add voicemail comment: %s", e)

        call.hangup(
            final_instructions=(
                f"Leave a brief, warm voicemail for {contact_name} from Relay Agency. "
                f"Mention you're following up on {conv_subject} and ask them to reply "
                "to the email thread or call back at their convenience. Keep it short."
            )
        )
    elif outcome == "available":
        contact_name = call.get_variable("contact_name")
        conv_subject = call.get_variable("conv_subject")

        call.set_task(
            "log_and_update",
            objective=(
                f"Follow up with {contact_name} on {conv_subject}. "
                "Understand if their question or issue has been addressed, capture any updates, "
                "and determine if the conversation can be closed."
            ),
            checklist=[
                guava.Say(
                    f"Hi {contact_name}, this is Morgan from Relay Agency. "
                    f"I'm following up on {conv_subject} to make sure everything is sorted."
                ),
                guava.Field(
                    key="issue_resolved",
                    field_type="multiple_choice",
                    description=(
                        "Ask if the original question or issue has been resolved to their satisfaction."
                    ),
                    choices=["yes, resolved", "partially resolved", "not resolved"],
                    required=True,
                ),
                guava.Field(
                    key="remaining_questions",
                    field_type="text",
                    description=(
                        "If not fully resolved, ask what's still outstanding. "
                        "Capture the full detail."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="can_close",
                    field_type="multiple_choice",
                    description=(
                        "Ask if it's okay to close the conversation thread, or if they'd like "
                        "to keep it open."
                    ),
                    choices=["yes, close it", "keep it open"],
                    required=True,
                ),
            ],
        )


@agent.on_task_complete("log_and_update")
def on_done(call: guava.Call) -> None:
    contact_name = call.get_variable("contact_name")
    conversation_id = call.get_variable("conversation_id")
    author_id = call.get_variable("author_id")

    resolved = call.get_field("issue_resolved") or "not resolved"
    remaining = call.get_field("remaining_questions") or ""
    can_close = call.get_field("can_close") or "keep it open"

    note_lines = [
        f"Follow-up call — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"Spoke with: {contact_name}",
        f"Resolution status: {resolved}",
        f"Can close: {can_close}",
    ]
    if remaining:
        note_lines.append(f"Outstanding: {remaining}")

    logging.info(
        "Follow-up complete for conversation %s — resolved: %s, close: %s",
        conversation_id, resolved, can_close,
    )

    try:
        add_comment(conversation_id, author_id, "\n".join(note_lines))
        logging.info("Comment added to conversation %s.", conversation_id)
    except Exception as e:
        logging.error("Failed to add comment to conversation %s: %s", conversation_id, e)

    if can_close == "yes, close it" and resolved != "not resolved":
        try:
            update_conversation_status(conversation_id, "archived")
            logging.info("Conversation %s archived.", conversation_id)
        except Exception as e:
            logging.error("Failed to archive conversation %s: %s", conversation_id, e)

    if resolved == "yes, resolved":
        call.hangup(
            final_instructions=(
                f"Thank {contact_name} for confirming everything is resolved. "
                "Let them know the conversation has been closed and to reach out anytime. "
                "Wish them a great day."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Thank {contact_name} for the update. Let them know the outstanding "
                f"item has been noted and the team will follow up. "
                + (f"Specifically acknowledge: {remaining}. " if remaining else "")
                + "Wish them a great day."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    parser = argparse.ArgumentParser(
        description="Outbound follow-up call for a pending Front conversation."
    )
    parser.add_argument("phone", help="Contact's phone number (E.164, e.g. +15551234567)")
    parser.add_argument("--name", required=True, help="Full name of the contact to reach")
    parser.add_argument("--conversation-id", required=True, help="Front conversation ID (e.g. cnv_XXXX)")
    parser.add_argument("--author-id", required=True, help="Front teammate ID to post comments as (e.g. tea_XXXX)")
    args = parser.parse_args()

    logging.info(
        "Initiating follow-up call to %s (%s) for conversation %s",
        args.name, args.phone, args.conversation_id,
    )

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=args.phone,
        variables={
            "contact_name": args.name,
            "conversation_id": args.conversation_id,
            "author_id": args.author_id,
        },
    )

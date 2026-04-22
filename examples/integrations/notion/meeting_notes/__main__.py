import guava
import os
import logging
from guava import logging_utils
import requests
from datetime import datetime, timezone


BASE_URL = "https://api.notion.com/v1"
DATABASE_ID = os.environ["NOTION_DATABASE_ID"]


def get_headers() -> dict:
    return {
        "Authorization": f"Bearer {os.environ['NOTION_TOKEN']}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }


def create_meeting_notes_page(
    meeting_title: str,
    attendees: str,
    date: str,
    summary: str,
    action_items: str,
) -> dict | None:
    properties: dict = {
        "Name": {"title": [{"text": {"content": meeting_title}}]},
        "Status": {"select": {"name": "Done"}},
    }

    if attendees:
        properties["Attendees"] = {"rich_text": [{"text": {"content": attendees}}]}
    if date:
        properties["Date"] = {"date": {"start": date}}

    children = []
    if summary:
        children.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"type": "text", "text": {"content": "Meeting Summary"}}]
            },
        })
        children.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": summary}}]
            },
        })

    if action_items:
        children.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"type": "text", "text": {"content": "Action Items"}}]
            },
        })
        for item in action_items.split(","):
            item = item.strip()
            if item:
                children.append({
                    "object": "block",
                    "type": "to_do",
                    "to_do": {
                        "rich_text": [{"type": "text", "text": {"content": item}}],
                        "checked": False,
                    },
                })

    payload: dict = {
        "parent": {"database_id": DATABASE_ID},
        "properties": properties,
    }
    if children:
        payload["children"] = children

    resp = requests.post(f"{BASE_URL}/pages", headers=get_headers(), json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json()


agent = guava.Agent(
    name="Sam",
    organization="Atlas Consulting",
    purpose=(
        "to help Atlas Consulting team members quickly log meeting notes to Notion by phone"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "meeting_notes_capture",
        objective=(
            "A team member has called to log meeting notes. "
            "Collect the meeting title, date, attendees, summary, and action items, "
            "then create a new page in Notion."
        ),
        checklist=[
            guava.Say(
                "Atlas Consulting, this is Sam. I can log your meeting notes to Notion right now."
            ),
            guava.Field(
                key="meeting_title",
                field_type="text",
                description="Ask for the title or topic of the meeting.",
                required=True,
            ),
            guava.Field(
                key="meeting_date",
                field_type="text",
                description=(
                    "Ask when the meeting took place. "
                    f"Today is {datetime.now(timezone.utc).strftime('%B %d, %Y')}. "
                    "Capture in YYYY-MM-DD format."
                ),
                required=False,
            ),
            guava.Field(
                key="attendees",
                field_type="text",
                description="Ask who attended the meeting (names or roles, comma-separated).",
                required=False,
            ),
            guava.Field(
                key="summary",
                field_type="text",
                description="Ask for a brief summary of what was discussed or decided.",
                required=True,
            ),
            guava.Field(
                key="action_items",
                field_type="text",
                description=(
                    "Ask if there are any action items. "
                    "Collect them as a comma-separated list."
                ),
                required=False,
            ),
        ],
    )


@agent.on_task_complete("meeting_notes_capture")
def on_meeting_notes_capture_done(call: guava.Call) -> None:
    meeting_title = call.get_field("meeting_title") or "Meeting Notes"
    meeting_date = call.get_field("meeting_date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    attendees = call.get_field("attendees") or ""
    summary = call.get_field("summary") or ""
    action_items = call.get_field("action_items") or ""

    logging.info("Creating meeting notes page: '%s' on %s", meeting_title, meeting_date)

    created = None
    try:
        created = create_meeting_notes_page(
            meeting_title=meeting_title,
            attendees=attendees,
            date=meeting_date,
            summary=summary,
            action_items=action_items,
        )
        logging.info("Meeting notes page created: %s", created.get("id") if created else None)
    except Exception as e:
        logging.error("Failed to create meeting notes page: %s", e)

    if created:
        notion_url = created.get("url", "")
        call.hangup(
            final_instructions=(
                f"Let the caller know the meeting notes for '{meeting_title}' have been added to Notion. "
                + (f"They can view the page at: {notion_url}. " if notion_url else "")
                + "Thank them and wish them a productive day."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                "Apologize — the meeting notes couldn't be saved automatically. "
                "Ask them to add the notes directly in Notion or try calling back. "
                "Thank them for their patience."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])

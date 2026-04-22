import logging
import os
from datetime import datetime

import guava
import requests
from guava import logging_utils

BASE_URL = "https://api.notion.com/v1"
DATABASE_ID = os.environ["NOTION_DATABASE_ID"]


def get_headers() -> dict:
    return {
        "Authorization": f"Bearer {os.environ['NOTION_TOKEN']}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }


def create_task(title: str, description: str, assignee: str, due_date: str, priority: str) -> dict | None:
    """Creates a new page in the Notion task database."""
    properties: dict = {
        "Name": {"title": [{"text": {"content": title}}]},
        "Status": {"select": {"name": "To Do"}},
    }

    if assignee:
        properties["Assignee"] = {"rich_text": [{"text": {"content": assignee}}]}
    if due_date:
        properties["Due Date"] = {"date": {"start": due_date}}
    if priority:
        properties["Priority"] = {"select": {"name": priority}}

    payload: dict = {
        "parent": {"database_id": DATABASE_ID},
        "properties": properties,
    }

    if description:
        payload["children"] = [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": description}}]
                },
            }
        ]

    resp = requests.post(f"{BASE_URL}/pages", headers=get_headers(), json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json()


agent = guava.Agent(
    name="Sam",
    organization="Atlas Consulting",
    purpose=(
        "to help Atlas Consulting team members quickly create tasks in Notion by phone"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "task_creation",
        objective=(
            "A team member has called to create a new task. "
            "Collect the task details and log it to Notion."
        ),
        checklist=[
            guava.Say(
                "Atlas Consulting, this is Sam. I can create a Notion task for you right now."
            ),
            guava.Field(
                key="task_title",
                field_type="text",
                description="Ask for a brief title for the task.",
                required=True,
            ),
            guava.Field(
                key="task_description",
                field_type="text",
                description="Ask for any additional details or description for the task.",
                required=False,
            ),
            guava.Field(
                key="assignee",
                field_type="text",
                description="Ask who this task should be assigned to.",
                required=False,
            ),
            guava.Field(
                key="due_date",
                field_type="text",
                description=(
                    "Ask when this task is due. "
                    "Capture in YYYY-MM-DD format (e.g., 2026-04-15)."
                ),
                required=False,
            ),
            guava.Field(
                key="priority",
                field_type="multiple_choice",
                description="Ask what priority level this task is.",
                choices=["High", "Medium", "Low"],
                required=False,
            ),
        ],
    )


@agent.on_task_complete("task_creation")
def on_task_creation_done(call: guava.Call) -> None:
    title = call.get_field("task_title") or ""
    description = call.get_field("task_description") or ""
    assignee = call.get_field("assignee") or ""
    due_date = call.get_field("due_date") or ""
    priority = call.get_field("priority") or "Medium"

    logging.info("Creating Notion task: '%s' — assignee: %s, due: %s", title, assignee, due_date)

    created = None
    try:
        created = create_task(title, description, assignee, due_date, priority)
        logging.info("Notion task created: %s", created.get("id") if created else None)
    except Exception as e:
        logging.error("Failed to create Notion task: %s", e)

    if created:
        notion_url = created.get("url", "")
        call.hangup(
            final_instructions=(
                f"Let the caller know the task '{title}' has been added to Notion"
                + (f" and assigned to {assignee}" if assignee else "")
                + (f" with a due date of {due_date}" if due_date else "")
                + ". "
                + (f"They can view it at: {notion_url}. " if notion_url else "")
                + "Thank them and wish them a productive day."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                "Apologize — the task couldn't be created automatically. "
                "Ask them to add it directly in Notion or try calling back. "
                "Thank them for their patience."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])

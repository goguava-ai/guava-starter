import guava
import os
import logging
import requests

logging.basicConfig(level=logging.INFO)

MONDAY_API_URL = "https://api.monday.com/v2"


def get_headers() -> dict:
    return {
        "Authorization": os.environ["MONDAY_API_TOKEN"],
        "Content-Type": "application/json",
        "API-Version": "2024-01",
    }


def create_item(board_id: int, item_name: str, column_values: dict) -> dict | None:
    import json

    query = """
    mutation ($boardId: ID!, $itemName: String!, $columnValues: JSON!) {
        create_item(
            board_id: $boardId,
            item_name: $itemName,
            column_values: $columnValues
        ) {
            id
            name
            url
        }
    }
    """
    variables = {
        "boardId": str(board_id),
        "itemName": item_name,
        "columnValues": json.dumps(column_values),
    }
    resp = requests.post(
        MONDAY_API_URL,
        headers=get_headers(),
        json={"query": query, "variables": variables},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("data", {}).get("create_item")


class ItemCreationController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Vantage Operations",
            agent_name="Riley",
            agent_purpose=(
                "to help Vantage Operations team members create new items in Monday.com by phone"
            ),
        )

        self.set_task(
            objective=(
                "A team member has called to create a new item in Monday.com. "
                "Collect the item name, description, assignee, due date, and priority, "
                "then create it on the configured board."
            ),
            checklist=[
                guava.Say(
                    "Vantage Operations, this is Riley. I can create a Monday.com item for you right now."
                ),
                guava.Field(
                    key="item_name",
                    field_type="text",
                    description="Ask for a title for the item.",
                    required=True,
                ),
                guava.Field(
                    key="description",
                    field_type="text",
                    description="Ask for a brief description or any additional details.",
                    required=False,
                ),
                guava.Field(
                    key="assignee",
                    field_type="text",
                    description="Ask who this item should be assigned to.",
                    required=False,
                ),
                guava.Field(
                    key="due_date",
                    field_type="text",
                    description=(
                        "Ask when this item is due. "
                        "Capture in YYYY-MM-DD format (e.g., 2026-04-15)."
                    ),
                    required=False,
                ),
                guava.Field(
                    key="priority",
                    field_type="multiple_choice",
                    description="Ask what priority this item is.",
                    choices=["High", "Medium", "Low"],
                    required=False,
                ),
            ],
            on_complete=self.create_item,
        )

        self.accept_call()

    def create_item(self):
        item_name = self.get_field("item_name") or ""
        description = self.get_field("description") or ""
        assignee = self.get_field("assignee") or ""
        due_date = self.get_field("due_date") or ""
        priority = self.get_field("priority") or "Medium"

        board_id = int(os.environ.get("MONDAY_BOARD_ID", "0"))

        column_values: dict = {}
        if description:
            column_values["text"] = description
        if due_date:
            column_values["date4"] = {"date": due_date}
        if priority:
            column_values["priority"] = {"label": priority}

        logging.info(
            "Creating Monday.com item: '%s' on board %s, assignee: %s, due: %s",
            item_name,
            board_id,
            assignee,
            due_date,
        )

        created = None
        try:
            created = create_item(board_id, item_name, column_values)
            logging.info("Monday.com item created: %s", created.get("id") if created else None)
        except Exception as e:
            logging.error("Failed to create Monday.com item: %s", e)

        if created:
            item_url = created.get("url", "")
            self.hangup(
                final_instructions=(
                    f"Let the caller know the item '{item_name}' has been created in Monday.com"
                    + (f" and assigned to {assignee}" if assignee else "")
                    + (f" with a due date of {due_date}" if due_date else "")
                    + ". "
                    + (f"They can view it at: {item_url}. " if item_url else "")
                    + "Thank them and wish them a productive day."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    "Apologize — the item couldn't be created automatically. "
                    "Ask them to add it directly in Monday.com or try calling back. "
                    "Thank them for their patience."
                )
            )


if __name__ == "__main__":
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=ItemCreationController,
    )

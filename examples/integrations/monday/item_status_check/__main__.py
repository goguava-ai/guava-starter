import guava
import os
import logging
from guava import logging_utils
import requests


MONDAY_API_URL = "https://api.monday.com/v2"


def get_headers() -> dict:
    return {
        "Authorization": os.environ["MONDAY_API_TOKEN"],
        "Content-Type": "application/json",
        "API-Version": "2024-01",
    }


def search_items(board_id: int, item_name: str) -> list[dict]:
    query = """
    query ($boardId: [ID!]!, $itemName: String!) {
        boards(ids: $boardId) {
            items_page(limit: 5, query_params: {rules: [{column_id: "name", compare_value: [$itemName]}]}) {
                items {
                    id
                    name
                    state
                    column_values {
                        id
                        title
                        text
                    }
                }
            }
        }
    }
    """
    variables = {"boardId": [str(board_id)], "itemName": item_name}
    resp = requests.post(
        MONDAY_API_URL,
        headers=get_headers(),
        json={"query": query, "variables": variables},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    boards = data.get("data", {}).get("boards", [])
    if not boards:
        return []
    return boards[0].get("items_page", {}).get("items", [])


def get_item_by_id(item_id: int) -> dict | None:
    query = """
    query ($itemId: [ID!]!) {
        items(ids: $itemId) {
            id
            name
            state
            board { name }
            column_values {
                id
                title
                text
            }
        }
    }
    """
    variables = {"itemId": [str(item_id)]}
    resp = requests.post(
        MONDAY_API_URL,
        headers=get_headers(),
        json={"query": query, "variables": variables},
        timeout=10,
    )
    resp.raise_for_status()
    items = resp.json().get("data", {}).get("items", [])
    return items[0] if items else None


class ItemStatusCheckController(guava.CallController):
    def __init__(self):
        super().__init__()

        self.set_persona(
            organization_name="Vantage Operations",
            agent_name="Riley",
            agent_purpose=(
                "to help Vantage Operations team members check the status of their Monday.com items by phone"
            ),
        )

        self.set_task(
            objective=(
                "A team member has called to check the status of a Monday.com item. "
                "Collect the item name or ID, look it up, and read back the status and key details."
            ),
            checklist=[
                guava.Say(
                    "Vantage Operations, this is Riley. I can look up your Monday.com item status right now."
                ),
                guava.Field(
                    key="lookup_method",
                    field_type="multiple_choice",
                    description="Ask how they'd like to find their item — by name or by item ID.",
                    choices=["name", "item ID"],
                    required=True,
                ),
                guava.Field(
                    key="item_name",
                    field_type="text",
                    description="If by name, ask for the item name.",
                    required=False,
                ),
                guava.Field(
                    key="item_id",
                    field_type="text",
                    description="If by ID, ask for the item ID number.",
                    required=False,
                ),
            ],
            on_complete=self.check_status,
        )

        self.accept_call()

    def check_status(self):
        lookup_method = self.get_field("lookup_method") or "name"
        item_name = self.get_field("item_name") or ""
        item_id_str = self.get_field("item_id") or ""

        board_id = int(os.environ.get("MONDAY_BOARD_ID", "0"))

        item = None
        try:
            if lookup_method == "item ID" and item_id_str.isdigit():
                item = get_item_by_id(int(item_id_str))
            elif item_name and board_id:
                results = search_items(board_id, item_name)
                item = results[0] if results else None
            logging.info("Looked up Monday.com item: %s", item.get("id") if item else None)
        except Exception as e:
            logging.error("Failed to look up Monday.com item: %s", e)

        if not item:
            self.hangup(
                final_instructions=(
                    "Let the caller know we couldn't find an item matching that name or ID. "
                    "They may want to check the item name and try again. Thank them for calling."
                )
            )
            return

        item_title = item.get("name", "Unknown")
        state = item.get("state", "")
        board_name = item.get("board", {}).get("name", "") if item.get("board") else ""

        col_values = item.get("column_values", [])
        status_col = next((c for c in col_values if c.get("id") == "status"), None)
        status_text = status_col.get("text", "") if status_col else state or "unknown"

        assignee_col = next((c for c in col_values if "person" in c.get("id", "").lower() or "assignee" in c.get("title", "").lower()), None)
        assignee = assignee_col.get("text", "") if assignee_col else ""

        due_col = next((c for c in col_values if "date" in c.get("id", "").lower() or "due" in c.get("title", "").lower()), None)
        due_date = due_col.get("text", "") if due_col else ""

        details = f"Item: '{item_title}'."
        if board_name:
            details += f" Board: {board_name}."
        details += f" Status: {status_text}."
        if assignee:
            details += f" Assigned to: {assignee}."
        if due_date:
            details += f" Due: {due_date}."

        self.hangup(
            final_instructions=(
                f"Read the following item details to the caller: {details} "
                "Thank them for calling Vantage Operations."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=ItemStatusCheckController,
    )

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


def get_board_summary(board_id: int) -> dict | None:
    query = """
    query ($boardId: [ID!]!) {
        boards(ids: $boardId) {
            id
            name
            state
            items_count
            groups {
                id
                title
                color
            }
        }
    }
    """
    resp = requests.post(
        MONDAY_API_URL,
        headers=get_headers(),
        json={"query": query, "variables": {"boardId": [str(board_id)]}},
        timeout=10,
    )
    resp.raise_for_status()
    boards = resp.json().get("data", {}).get("boards", [])
    return boards[0] if boards else None


def post_update(item_id: int, update_text: str) -> dict | None:
    query = """
    mutation ($itemId: ID!, $body: String!) {
        create_update(item_id: $itemId, body: $body) {
            id
            body
            created_at
        }
    }
    """
    variables = {"itemId": str(item_id), "body": update_text}
    resp = requests.post(
        MONDAY_API_URL,
        headers=get_headers(),
        json={"query": query, "variables": variables},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("data", {}).get("create_update")


def change_item_status(item_id: int, board_id: int, status_label: str) -> dict | None:
    import json

    query = """
    mutation ($boardId: ID!, $itemId: ID!, $columnId: String!, $value: JSON!) {
        change_column_value(
            board_id: $boardId,
            item_id: $itemId,
            column_id: $columnId,
            value: $value
        ) {
            id
        }
    }
    """
    variables = {
        "boardId": str(board_id),
        "itemId": str(item_id),
        "columnId": "status",
        "value": json.dumps({"label": status_label}),
    }
    resp = requests.post(
        MONDAY_API_URL,
        headers=get_headers(),
        json={"query": query, "variables": variables},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("data", {}).get("change_column_value")


class ProjectUpdateController(guava.CallController):
    def __init__(self):
        super().__init__()

        self._board_id = int(os.environ.get("MONDAY_BOARD_ID", "0"))
        self._board: dict | None = None

        try:
            if self._board_id:
                self._board = get_board_summary(self._board_id)
                logging.info("Loaded board: %s", self._board.get("name") if self._board else None)
        except Exception as e:
            logging.error("Failed to load board: %s", e)

        board = self._board
        context = (
            f"Board: '{board['name']}' with {board.get('items_count', 0)} items total."
            if board
            else "Board information could not be loaded."
        )

        self.set_persona(
            organization_name="Vantage Operations",
            agent_name="Riley",
            agent_purpose=(
                "to help Vantage Operations team members post project updates in Monday.com by phone"
            ),
        )

        self.set_task(
            objective=(
                "A team member has called to post a project update in Monday.com. "
                f"Project context: {context} "
                "Collect the item ID, update message, and any status change, then post the update."
            ),
            checklist=[
                guava.Say(
                    "Vantage Operations, this is Riley. I can post a project update to Monday.com for you."
                ),
                guava.Field(
                    key="item_id",
                    field_type="text",
                    description="Ask for the Monday.com item ID they want to update.",
                    required=True,
                ),
                guava.Field(
                    key="update_message",
                    field_type="text",
                    description="Ask for the update message they'd like to post on the item.",
                    required=True,
                ),
                guava.Field(
                    key="change_status",
                    field_type="multiple_choice",
                    description="Ask if they'd also like to change the item's status.",
                    choices=["yes", "no"],
                    required=True,
                ),
                guava.Field(
                    key="new_status",
                    field_type="multiple_choice",
                    description="If yes, ask what the new status should be.",
                    choices=["Working on it", "Done", "Stuck", "Not Started"],
                    required=False,
                ),
            ],
            on_complete=self.post_update,
        )

        self.accept_call()

    def post_update(self):
        item_id_str = self.get_field("item_id") or ""
        update_message = self.get_field("update_message") or ""
        change_status = self.get_field("change_status") or "no"
        new_status = self.get_field("new_status") or ""

        if not item_id_str.isdigit():
            self.hangup(
                final_instructions=(
                    "Let the caller know the item ID provided doesn't appear to be valid. "
                    "Ask them to call back with the correct item ID. Thank them."
                )
            )
            return

        item_id = int(item_id_str)

        update_posted = None
        try:
            update_posted = post_update(item_id, update_message)
            logging.info("Posted update to item %s", item_id)
        except Exception as e:
            logging.error("Failed to post update to item %s: %s", item_id, e)

        status_changed = False
        if change_status == "yes" and new_status and self._board_id:
            try:
                change_item_status(item_id, self._board_id, new_status)
                status_changed = True
                logging.info("Changed status of item %s to '%s'", item_id, new_status)
            except Exception as e:
                logging.error("Failed to change status of item %s: %s", item_id, e)

        if update_posted:
            self.hangup(
                final_instructions=(
                    f"Let the caller know the update has been posted to item {item_id}. "
                    + (f"The status has been changed to '{new_status}'. " if status_changed else "")
                    + "Thank them and wish them a productive day."
                )
            )
        else:
            self.hangup(
                final_instructions=(
                    "Apologize — we were unable to post the update automatically. "
                    "Ask them to post it directly in Monday.com or try calling back. "
                    "Thank them for their patience."
                )
            )


if __name__ == "__main__":
    logging_utils.configure_logging()
    guava.Client().listen_inbound(
        agent_number=os.environ["GUAVA_AGENT_NUMBER"],
        controller_class=ProjectUpdateController,
    )

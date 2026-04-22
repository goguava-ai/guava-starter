import logging
import os

import guava
import requests
from guava import logging_utils

MONDAY_API_URL = "https://api.monday.com/v2"


def get_headers() -> dict:
    return {
        "Authorization": os.environ["MONDAY_API_TOKEN"],
        "Content-Type": "application/json",
        "API-Version": "2024-01",
    }


def get_board_users(board_id: int) -> list[dict]:
    query = """
    query ($boardId: [ID!]!) {
        boards(ids: $boardId) {
            owners {
                id
                name
                email
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
    if not boards:
        return []
    return boards[0].get("owners", [])


def get_item(item_id: int) -> dict | None:
    query = """
    query ($itemId: [ID!]!) {
        items(ids: $itemId) {
            id
            name
            column_values {
                id
                title
                text
                type
            }
        }
    }
    """
    resp = requests.post(
        MONDAY_API_URL,
        headers=get_headers(),
        json={"query": query, "variables": {"itemId": [str(item_id)]}},
        timeout=10,
    )
    resp.raise_for_status()
    items = resp.json().get("data", {}).get("items", [])
    return items[0] if items else None


def assign_person(item_id: int, board_id: int, person_id: int) -> dict | None:
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
        "columnId": "person",
        "value": json.dumps({"personsAndTeams": [{"id": person_id, "kind": "person"}]}),
    }
    resp = requests.post(
        MONDAY_API_URL,
        headers=get_headers(),
        json={"query": query, "variables": variables},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("data", {}).get("change_column_value")


# Pre-fetch board users at startup so they can be embedded in the task objective.
_board_id = int(os.environ.get("MONDAY_BOARD_ID", "0"))
_board_users: list[dict] = []

try:
    if _board_id:
        _board_users = get_board_users(_board_id)
        logging.info("Loaded %d board users", len(_board_users))
except Exception as e:
    logging.error("Failed to load board users: %s", e)

_user_names = ", ".join(u["name"] for u in _board_users) if _board_users else "team members"

agent = guava.Agent(
    name="Riley",
    organization="Vantage Operations",
    purpose=(
        "to help Vantage Operations team members assign Monday.com tasks to team members by phone"
    ),
)


@agent.on_call_received
def on_call_received(call_info: guava.CallInfo) -> guava.IncomingCallAction:
    return guava.AcceptCall()


@agent.on_call_start
def on_call_start(call: guava.Call) -> None:
    call.set_task(
        "collect_assignment_details",
        objective=(
            "A team member has called to assign a Monday.com task to someone. "
            f"Board members available for assignment: {_user_names}. "
            "Collect the item ID and assignee name, then update the person column."
        ),
        checklist=[
            guava.Say(
                "Vantage Operations, this is Riley. I can assign a Monday.com task for you right now."
            ),
            guava.Field(
                key="item_id",
                field_type="text",
                description="Ask for the Monday.com item ID to assign.",
                required=True,
            ),
            guava.Field(
                key="assignee_name",
                field_type="text",
                description=(
                    f"Ask who to assign this task to. Available team members: {_user_names}."
                ),
                required=True,
            ),
        ],
    )


@agent.on_task_complete("collect_assignment_details")
def assign_task(call: guava.Call) -> None:
    item_id_str = call.get_field("item_id") or ""
    assignee_name = call.get_field("assignee_name") or ""

    if not item_id_str.isdigit():
        call.hangup(
            final_instructions=(
                "Let the caller know the item ID provided doesn't appear to be valid. "
                "Ask them to call back with the correct item ID. Thank them."
            )
        )
        return

    item_id = int(item_id_str)

    # Match assignee name to a board user
    matched_user = None
    name_lower = assignee_name.lower()
    for user in _board_users:
        if name_lower in user.get("name", "").lower():
            matched_user = user
            break

    if not matched_user:
        call.hangup(
            final_instructions=(
                f"Let the caller know we couldn't find a team member named '{assignee_name}' on this board. "
                "Ask them to try the person's full name or contact the board admin. Thank them for calling."
            )
        )
        return

    person_id = int(matched_user["id"])
    person_name = matched_user["name"]

    assigned = None
    try:
        assigned = assign_person(item_id, _board_id, person_id)
        logging.info("Assigned item %s to %s (id: %s)", item_id, person_name, person_id)
    except Exception as e:
        logging.error("Failed to assign item %s to %s: %s", item_id, person_name, e)

    if assigned:
        call.hangup(
            final_instructions=(
                f"Let the caller know item {item_id} has been assigned to {person_name} in Monday.com. "
                "Thank them and wish them a productive day."
            )
        )
    else:
        call.hangup(
            final_instructions=(
                f"Apologize — we were unable to assign item {item_id} to {person_name} automatically. "
                "Ask them to make the assignment directly in Monday.com. Thank them for their patience."
            )
        )


if __name__ == "__main__":
    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])

# Project Update

**Direction:** Inbound

A team member calls to post an update on a Monday.com item. The agent collects the item ID, update message, and optional status change, then posts the update and optionally changes the column value via GraphQL mutations.

## What it does

1. Loads board summary via `boards(ids: ...)` query at call start
2. Collects item ID, update text, and optional new status
3. Posts update via `create_update` mutation
4. Optionally changes status via `change_column_value` mutation

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `MONDAY_API_TOKEN` | Monday.com API token |
| `MONDAY_BOARD_ID` | Board ID containing the item |

## Usage

```bash
python -m examples.integrations.monday.project_update
```

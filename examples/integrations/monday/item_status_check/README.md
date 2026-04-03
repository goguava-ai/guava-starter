# Item Status Check

**Direction:** Inbound

A team member calls to check the status of a Monday.com item. The agent looks up the item by name or ID via the Monday.com GraphQL API and reads back the status, assignee, and due date.

## What it does

1. Collects the item name or ID from the caller
2. Queries via GraphQL — by name using `items_page` with a filter rule, or by ID using `items(ids: ...)`
3. Reads back item name, board, status, assignee, and due date

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `MONDAY_API_TOKEN` | Monday.com API token |
| `MONDAY_BOARD_ID` | Default board ID for name-based searches |

## Usage

```bash
python -m examples.integrations.monday.item_status_check
```

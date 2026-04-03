# Item Creation

**Direction:** Inbound

A team member calls to create a new item in Monday.com. The agent collects the item title, description, assignee, due date, and priority, then creates it on the configured board via the GraphQL API.

## What it does

1. Collects item name, description, assignee, due date, and priority
2. Creates the item via GraphQL `create_item` mutation with `column_values` JSON for date and priority

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `MONDAY_API_TOKEN` | Monday.com API token |
| `MONDAY_BOARD_ID` | Board ID to create items on |

## Usage

```bash
python -m examples.integrations.monday.item_creation
```

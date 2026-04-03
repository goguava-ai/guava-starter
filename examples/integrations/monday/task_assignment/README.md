# Task Assignment

**Direction:** Inbound

A team member calls to assign a Monday.com task to a team member. The agent loads board owners at call start, collects the item ID and assignee name, matches the name to a board member, and updates the person column via GraphQL.

## What it does

1. Loads board owners via `boards(ids: ...) { owners { id name email } }` at call start
2. Collects item ID and assignee name
3. Matches the name to a board member's ID
4. Updates the person column via `change_column_value` mutation with `personsAndTeams` value

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `MONDAY_API_TOKEN` | Monday.com API token |
| `MONDAY_BOARD_ID` | Board ID containing the item |

## Usage

```bash
python -m examples.integrations.monday.task_assignment
```

# Task Creation

**Direction:** Inbound

A team member calls to create a new task in Notion. The agent collects the task title, description, assignee, due date, and priority, then creates a new page in the configured Notion database.

## What it does

1. Collects task title, description, assignee, due date, and priority
2. Creates a new database page via `POST /v1/pages` with structured properties and a description body block

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `NOTION_TOKEN` | Notion internal integration token |
| `NOTION_DATABASE_ID` | Target database ID |

## Usage

```bash
python -m examples.integrations.notion.task_creation
```

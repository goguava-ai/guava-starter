# Page Lookup

**Direction:** Inbound

A team member calls to look up a Notion page by title or keyword. The agent queries the configured database and reads back the page title, status, assignee, due date, and URL.

## What it does

1. Collects a search keyword from the caller
2. Queries the database via `POST /v1/databases/{database_id}/query` with a title contains filter
3. Reads back key properties (Status, Assignee, Due Date, Priority) from the matching page

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `NOTION_TOKEN` | Notion internal integration token |
| `NOTION_DATABASE_ID` | Target database ID |

## Usage

```bash
python -m examples.integrations.notion.page_lookup
```

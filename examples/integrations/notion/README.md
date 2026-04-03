# Notion Integration

Voice agents that integrate with the [Notion API](https://developers.notion.com) to create tasks, look up pages, capture meeting notes, and log feedback — for teams that use Notion as their knowledge base and project management tool.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`task_creation`](task_creation/) | Inbound | Caller dictates a task; agent creates a new page in a Notion database |
| [`page_lookup`](page_lookup/) | Inbound | Caller asks about the status of a project or task tracked in Notion |
| [`meeting_notes`](meeting_notes/) | Inbound | Caller records meeting notes; agent creates a structured Notion page |
| [`feedback_capture`](feedback_capture/) | Outbound | Call customers for feedback; log structured responses as Notion database entries |

## Authentication

All examples use an integration token as a Bearer token:

```python
headers = {
    "Authorization": f"Bearer {os.environ['NOTION_TOKEN']}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}
```

Create an internal integration at [notion.so/my-integrations](https://www.notion.so/my-integrations) and share the target database with it.

## Base URL

```
https://api.notion.com/v1
```

## Common Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `NOTION_TOKEN` | Notion internal integration token |
| `NOTION_DATABASE_ID` | Target database ID (from the database URL) |

## Usage

Inbound examples:

```bash
python -m examples.integrations.notion.task_creation
python -m examples.integrations.notion.page_lookup
python -m examples.integrations.notion.meeting_notes
```

Outbound example:

```bash
python -m examples.integrations.notion.feedback_capture "+15551234567" --name "Chris Wu" --record-id "recXXXXXXXX"
```

## Notion API Reference

- [Create a Page](https://developers.notion.com/reference/post-page)
- [Query a Database](https://developers.notion.com/reference/post-database-query)
- [Retrieve a Page](https://developers.notion.com/reference/retrieve-a-page)
- [Append Block Children](https://developers.notion.com/reference/patch-block-children)

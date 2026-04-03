# Meeting Notes

**Direction:** Inbound

A team member calls to log meeting notes to Notion. The agent collects the meeting title, date, attendees, a summary, and action items, then creates a structured Notion page with heading blocks and to-do checkboxes for each action item.

## What it does

1. Collects meeting title, date, attendees, summary, and comma-separated action items
2. Creates a new page via `POST /v1/pages` with:
   - Properties: Name (title), Status (select: Done), Attendees (rich_text), Date (date)
   - Body blocks: Meeting Summary heading + paragraph, Action Items heading + to-do blocks

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `NOTION_TOKEN` | Notion internal integration token |
| `NOTION_DATABASE_ID` | Target database ID |

## Usage

```bash
python -m examples.integrations.notion.meeting_notes
```

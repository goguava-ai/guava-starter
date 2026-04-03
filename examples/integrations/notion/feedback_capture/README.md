# Feedback Capture

**Direction:** Inbound

A client or team member calls to leave feedback. The agent collects their name, feedback category, a 1–5 rating, detailed comments, and whether they want a follow-up, then creates a structured page in Notion.

## What it does

1. Collects submitter name, category, rating, feedback text, and follow-up preference
2. Creates a feedback page via `POST /v1/pages` with:
   - Properties: Name (auto-generated title), Status (New), Submitter, Category, Rating (number), Follow-Up Needed (checkbox), Date
   - Body: feedback text as a paragraph block

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `NOTION_TOKEN` | Notion internal integration token |
| `NOTION_DATABASE_ID` | Target database ID |

## Usage

```bash
python -m examples.integrations.notion.feedback_capture
```

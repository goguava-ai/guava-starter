# Calendar Check

**Direction:** Inbound

A team member calls to hear their Outlook schedule for a specific day. The agent asks which day (today, tomorrow, a specific date) and optionally whose calendar to check, then reads back all events in order.

## What it does

1. Asks which day and optionally whose calendar (defaults to the caller's own via `me`)
2. Calls `GET /users/{id}/calendarView` with `startDateTime` and `endDateTime` for the target day
3. Filters out cancelled events
4. Reads back all events with subject, time range, and location (or "online" for Teams/Skype meetings)

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `GRAPH_ACCESS_TOKEN` | Microsoft Graph OAuth 2.0 access token |

## Usage

```bash
python -m examples.integrations.outlook.calendar_check
```

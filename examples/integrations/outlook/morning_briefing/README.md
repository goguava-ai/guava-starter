# Morning Briefing

**Direction:** Outbound

Each morning, this agent calls an employee to brief them on their day before they open their laptop. It pre-fetches their Outlook calendar for the day and their unread high-importance email count, then delivers a concise spoken summary and answers any quick questions.

## What it does

1. Fetches today's events pre-call via `GET /users/{userId}/calendarView` (filtered to today, ordered by start time, cancelled events excluded)
2. Fetches unread high-importance inbox count via `GET /users/{userId}/mailFolders/inbox/messages?$filter=isRead eq false and importance eq 'high'`
3. Calls the employee via `reach_person`
4. Reads back today's meeting count, each event's name and time, and the unread important email count
5. Asks if they have any questions about the schedule and responds with the context on hand
6. If unavailable, leaves a brief voicemail with the meeting count

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `GRAPH_ACCESS_TOKEN` | Microsoft Graph OAuth 2.0 access token |

## Usage

```bash
python -m examples.integrations.outlook.morning_briefing \
  "+15551234567" \
  --name "Jane Smith" \
  --user-id jane.smith@company.com
```

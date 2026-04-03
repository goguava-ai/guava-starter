# Meeting Reschedule

**Direction:** Inbound

A team member calls to move an existing meeting to a new date and time. The agent finds the event by name, collects the new date and time window, and updates the event — automatically notifying all attendees of the change.

## What it does

1. Asks for the meeting name (or keyword), the new date, new start time, and new end time
2. Searches `GET /me/calendarView` for upcoming events matching the name
3. Updates the found event via `PATCH /me/events/{id}` with new `start` and `end` datetimes
4. Outlook automatically sends updated invites to all attendees

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `GRAPH_ACCESS_TOKEN` | Microsoft Graph OAuth 2.0 access token |
| `GRAPH_TIMEZONE` | Windows timezone name (default: `Eastern Standard Time`) |

## Usage

```bash
python -m examples.integrations.outlook.meeting_reschedule
```

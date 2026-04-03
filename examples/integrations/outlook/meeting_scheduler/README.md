# Meeting Scheduler

**Direction:** Inbound

A team member calls to schedule a meeting. The agent collects the title, attendees, preferred date, and duration, then uses Graph's `findMeetingTimes` to identify a slot that works for everyone. The agent proposes the best option and books it on confirmation.

## What it does

1. Collects meeting details: title, attendee emails, preferred date, and duration
2. Calls `POST /me/findMeetingTimes` with a work-hours time constraint on the preferred date
3. Proposes the top suggestion to the caller
4. On confirmation, creates the event via `POST /me/events` — calendar invites go to all attendees
5. If the first suggestion is rejected, offers an alternative slot or asks for a different date

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `GRAPH_ACCESS_TOKEN` | Microsoft Graph OAuth 2.0 access token |
| `GRAPH_TIMEZONE` | Windows timezone name (default: `Eastern Standard Time`) |

## Usage

```bash
python -m examples.integrations.outlook.meeting_scheduler
```

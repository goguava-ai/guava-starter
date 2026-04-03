# Microsoft Outlook / Exchange Integration

Voice agents that integrate with the [Microsoft Graph API](https://learn.microsoft.com/en-us/graph/overview) to automate Outlook calendar and email workflows — scheduling meetings, reading schedules, setting auto-replies, and following up on email threads without opening a browser.

## Examples

| Example | Direction | Description | Graph API |
|---|---|---|---|
| [`meeting_scheduler`](meeting_scheduler/) | Inbound | Caller schedules a meeting; agent finds open times across attendees and books the event | `POST /me/findMeetingTimes` + `POST /me/events` |
| [`calendar_check`](calendar_check/) | Inbound | Caller hears their Outlook schedule for any day, or checks a colleague's calendar | `GET /users/{id}/calendarView` |
| [`meeting_rsvp`](meeting_rsvp/) | Inbound | Caller accepts, tentatively accepts, or declines a pending meeting invite | `GET /me/calendarView` + `POST /me/events/{id}/accept\|decline\|tentativelyAccept` |
| [`meeting_reschedule`](meeting_reschedule/) | Inbound | Caller moves an existing meeting to a new date and time | `GET /me/calendarView` + `PATCH /me/events/{id}` |
| [`out_of_office_setup`](out_of_office_setup/) | Inbound | Caller configures or disables their Outlook auto-reply with custom dates and backup contact | `PATCH /me/mailboxSettings` |
| [`email_follow_up`](email_follow_up/) | Outbound | Agent calls a contact to follow up on a specific email, reads back context, and records their response | `GET /users/{id}/messages/{id}` + `PATCH` |
| [`morning_briefing`](morning_briefing/) | Outbound | Agent calls an employee each morning with their day's meeting schedule and unread important email count | `GET /users/{id}/calendarView` + `GET /users/{id}/mailFolders/inbox/messages` |

## Authentication

All examples use a pre-obtained Microsoft Graph delegated access token:

```python
headers = {"Authorization": f"Bearer {GRAPH_ACCESS_TOKEN}"}
```

Obtain a token via the [Microsoft identity platform](https://learn.microsoft.com/en-us/azure/active-directory/develop/) using OAuth 2.0 authorization code flow (delegated) or client credentials (app-only). Set the token as `GRAPH_ACCESS_TOKEN` in your environment.

Required Graph permissions:
- `Calendars.ReadWrite` — for reading and writing calendar events
- `Mail.Read` / `Mail.ReadWrite` — for reading messages and updating flags
- `MailboxSettings.ReadWrite` — for configuring auto-replies

## Base URL

```
https://graph.microsoft.com/v1.0
```

## Common Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `GRAPH_ACCESS_TOKEN` | Microsoft Graph OAuth 2.0 access token |
| `GRAPH_TIMEZONE` | Windows timezone name for event times (default: `Eastern Standard Time`) |

## Usage

Inbound examples:

```bash
python -m examples.integrations.outlook.meeting_scheduler
python -m examples.integrations.outlook.calendar_check
python -m examples.integrations.outlook.meeting_rsvp
python -m examples.integrations.outlook.meeting_reschedule
python -m examples.integrations.outlook.out_of_office_setup
```

Outbound examples:

```bash
python -m examples.integrations.outlook.email_follow_up \
  "+15551234567" --name "Jane Smith" --user-id me@company.com --message-id AAMk...

python -m examples.integrations.outlook.morning_briefing \
  "+15551234567" --name "Jane Smith" --user-id jane.smith@company.com
```

## Microsoft Graph API Reference

- [Calendar API](https://learn.microsoft.com/en-us/graph/api/resources/calendar)
- [Events](https://learn.microsoft.com/en-us/graph/api/resources/event)
- [findMeetingTimes](https://learn.microsoft.com/en-us/graph/api/user-findmeetingtimes)
- [Messages](https://learn.microsoft.com/en-us/graph/api/resources/message)
- [Mailbox Settings](https://learn.microsoft.com/en-us/graph/api/resources/mailboxsettings)

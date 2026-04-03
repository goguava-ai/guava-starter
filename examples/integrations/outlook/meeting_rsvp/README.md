# Meeting RSVP

**Direction:** Inbound

A team member calls to accept, tentatively accept, or decline a meeting invite. The agent searches their upcoming calendar by meeting name, confirms the right event, records their response, and sends the reply to the organizer.

## What it does

1. Asks for the meeting name and intended response (accept / tentative / decline) plus an optional note
2. Searches `GET /me/calendarView` for upcoming events containing the meeting name
3. Posts to `POST /me/events/{id}/accept`, `/tentativelyAccept`, or `/decline` with `sendResponse: true`
4. Confirms the RSVP was submitted and lets the caller know the organizer has been notified

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `GRAPH_ACCESS_TOKEN` | Microsoft Graph OAuth 2.0 access token |

## Usage

```bash
python -m examples.integrations.outlook.meeting_rsvp
```

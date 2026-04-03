# Ticket Status

**Direction:** Inbound

A customer calls to check the status of a Freshdesk support ticket. They can look up by ticket number or by email address (returns the most recent ticket).

## What it does

1. Asks if the caller wants to look up by ticket number or email
2. Fetches the ticket via `GET /api/v2/tickets/{id}` or searches by email via `GET /api/v2/tickets?email={email}`
3. Reads back the ticket status, priority, subject, and last-updated date

## Status Labels

| Freshdesk Status | Label |
|---|---|
| 2 | Open |
| 3 | Pending |
| 4 | Resolved |
| 5 | Closed |
| 6 | Waiting on Customer |
| 7 | Waiting on Third Party |

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `FRESHDESK_DOMAIN` | Freshdesk subdomain |
| `FRESHDESK_API_KEY` | Freshdesk API key |

## Usage

```bash
python __main__.py
```

# Escalation

**Direction:** Inbound

A frustrated customer calls to escalate an open support ticket. The agent empathizes, collects the ticket number and escalation reason, bumps the priority to Urgent, tags it for manager review, and adds a private escalation note.

## What it does

1. Collects ticket ID, caller name, escalation reason, detail, and business impact
2. Fetches the ticket via `GET /api/v2/tickets/{id}`
3. Updates priority to Urgent (4) and status to Open via `PUT /api/v2/tickets/{id}`
4. Adds a private escalation note via `POST /api/v2/tickets/{id}/notes`

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

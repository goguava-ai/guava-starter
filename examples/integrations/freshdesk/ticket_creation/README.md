# Ticket Creation

**Direction:** Inbound

A customer calls with a support issue. The agent collects their contact details, categorizes the issue, and creates a Freshdesk ticket tagged by issue type and prioritized automatically.

## What it does

1. Collects name, email, issue type, description, and priority
2. Creates a ticket via `POST /api/v2/tickets` with source set to Phone
3. Tags the ticket with `guava`, `voice`, and the issue category
4. Reads back the ticket number to the caller

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

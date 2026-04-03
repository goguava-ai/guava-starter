# CSAT Survey

**Direction:** Outbound

Follow up with a customer after their Freshdesk ticket is resolved. The agent collects a 1–5 satisfaction rating and asks if their issue was fully resolved. Results are saved as a private note and written to custom CSAT fields on the ticket.

## What it does

1. Fetches the ticket subject pre-call via `GET /api/v2/tickets/{id}` to personalize the survey
2. Calls the customer and runs a 3-question CSAT survey
3. Adds a private note with the results via `POST /api/v2/tickets/{id}/notes`
4. Updates custom fields `cf_csat_score`, `cf_csat_resolved`, `cf_csat_channel` via `PUT /api/v2/tickets/{id}`

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `FRESHDESK_DOMAIN` | Freshdesk subdomain |
| `FRESHDESK_API_KEY` | Freshdesk API key |

## Usage

```bash
python __main__.py +15551234567 --ticket-id 12345 --name "Jane Smith"
```

> **Note:** This example writes to custom fields `cf_csat_score`, `cf_csat_resolved`, and `cf_csat_channel`. Create them under **Admin → Ticket Fields** in Freshdesk.

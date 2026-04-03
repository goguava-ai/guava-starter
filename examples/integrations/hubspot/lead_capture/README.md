# Lead Capture

**Direction:** Inbound

A new prospect calls Apex Solutions. The agent collects their name, email, company, and interest, then creates (or updates) a HubSpot contact and opens a new deal in the default pipeline — no manual CRM entry required.

## What it does

1. Greets the caller and collects contact details and interest
2. Upserts a HubSpot contact via `POST /crm/v3/objects/contacts/batch/upsert` (keyed on email, so repeat callers are updated rather than duplicated)
3. Creates a deal in the `appointmentscheduled` stage via `POST /crm/v3/objects/deals`
4. Associates the deal with the contact

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `HUBSPOT_ACCESS_TOKEN` | HubSpot private app access token |

## Usage

```bash
python __main__.py
```

# Renewal Outreach

**Direction:** Outbound

Proactively call customers whose deals are approaching their close date. The agent gauges renewal intent, captures concerns, updates the deal stage in HubSpot, and logs a call note — all in one call.

## What it does

1. Fetches deal details pre-call via `GET /crm/v3/objects/deals/{dealId}` (name, amount, close date)
2. Reaches the customer and conducts a renewal intent conversation
3. Updates the deal stage via `PATCH /crm/v3/objects/deals/{dealId}` based on their intent
4. Logs the call outcome as a note via `POST /crm/v3/objects/notes`

## Deal Stage Mapping

| Intent | HubSpot Stage |
|---|---|
| Renew as-is | `contractsent` |
| Upgrade | `decisionmakerboughtin` |
| Undecided | `presentationscheduled` |
| Planning to cancel | `closedlost` |

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `HUBSPOT_ACCESS_TOKEN` | HubSpot private app access token |

## Usage

```bash
python __main__.py +15551234567 --deal-id 12345678 --name "Jane Smith"
```

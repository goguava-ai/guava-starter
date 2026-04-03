# Deal Qualification

**Direction:** Inbound

A prospect calls for a discovery conversation. The agent runs a BANT (Budget, Authority, Need, Timeline) qualification, then creates a HubSpot contact and deal. Fully qualified leads land in the `qualifiedtobuy` stage; others go to `appointmentscheduled` for nurturing.

## What it does

1. Collects contact details and runs BANT qualification fields
2. Upserts a HubSpot contact via `POST /crm/v3/objects/contacts/batch/upsert`
3. Creates a deal via `POST /crm/v3/objects/deals` with the qualification notes in the description
4. Sets the deal stage based on qualification score

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `HUBSPOT_ACCESS_TOKEN` | HubSpot private app access token |

## Usage

```bash
python __main__.py
```

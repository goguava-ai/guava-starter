# Lead Capture

**Direction:** Inbound

An inbound lead calls in. The agent collects their contact details, company, inquiry, and urgency, then creates a new record in the Airtable Leads table.

## What it does

1. Collects name, email, phone, company, inquiry description, and urgency
2. Creates a new record via `POST /v0/{baseId}/{tableName}` with all collected fields

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `AIRTABLE_API_KEY` | Airtable Personal Access Token |
| `AIRTABLE_BASE_ID` | Base ID (e.g., `appXXXXXXXXXXXXXX`) |
| `AIRTABLE_LEADS_TABLE` | Table name (default: `Leads`) |

## Usage

```bash
python -m examples.integrations.airtable.lead_capture
```

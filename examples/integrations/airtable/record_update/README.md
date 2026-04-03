# Record Update

**Direction:** Inbound

A team member calls to update a field on an existing Airtable record. The agent searches for the record by name, confirms the field and new value with the caller, and patches the record.

## What it does

1. Finds the record via `GET /v0/{baseId}/{tableName}?filterByFormula=SEARCH(...)`
2. Collects the field name and new value from the caller
3. Updates the record via `PATCH /v0/{baseId}/{tableName}/{recordId}`

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `AIRTABLE_API_KEY` | Airtable Personal Access Token |
| `AIRTABLE_BASE_ID` | Base ID (e.g., `appXXXXXXXXXXXXXX`) |
| `AIRTABLE_TABLE_NAME` | Table name to update records in (default: `Records`) |

## Usage

```bash
python -m examples.integrations.airtable.record_update
```

# Record Lookup

**Direction:** Inbound

A team member calls to look up a record in Airtable. The agent collects a search query and field name, queries the table using `filterByFormula`, and reads back the matching record's fields.

## What it does

1. Collects a search query and optional field name from the caller
2. Searches via `GET /v0/{baseId}/{tableName}?filterByFormula=SEARCH(...)`
3. Reads back up to 6 fields from the top matching record

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `AIRTABLE_API_KEY` | Airtable Personal Access Token |
| `AIRTABLE_BASE_ID` | Base ID (e.g., `appXXXXXXXXXXXXXX`) |
| `AIRTABLE_TABLE_NAME` | Table name to search (default: `Records`) |

## Usage

```bash
python -m examples.integrations.airtable.record_lookup
```

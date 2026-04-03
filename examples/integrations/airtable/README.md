# Airtable Integration

Voice agents that integrate with the [Airtable REST API](https://airtable.com/developers/web/api/introduction) to look up and update records, capture leads, and collect structured data from callers — for operations, CRM, and project management use cases built on Airtable.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`record_lookup`](record_lookup/) | Inbound | Caller asks about the status of a record (order, request, ticket) in an Airtable base |
| [`lead_capture`](lead_capture/) | Inbound | Capture inbound lead details and write a new record to an Airtable CRM base |
| [`survey_collection`](survey_collection/) | Outbound | Call contacts from an Airtable table; collect responses and write back results |
| [`record_update`](record_update/) | Inbound | Caller updates an existing Airtable record (e.g., address, preferences, status) |

## Authentication

All examples use a Personal Access Token as a Bearer token:

```python
headers = {
    "Authorization": f"Bearer {os.environ['AIRTABLE_API_KEY']}",
    "Content-Type": "application/json",
}
```

Create a Personal Access Token at [airtable.com/create/tokens](https://airtable.com/create/tokens). Grant at minimum `data.records:read` and `data.records:write` scopes on the relevant bases.

## Base URL

```
https://api.airtable.com/v0/{base_id}/{table_name}
```

Find your Base ID in the Airtable API docs for your base (the `app...` string in the URL).

## Common Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `AIRTABLE_API_KEY` | Personal Access Token |
| `AIRTABLE_BASE_ID` | Base ID (e.g., `appXXXXXXXXXXXXXX`) |

## Usage

Inbound examples:

```bash
python -m examples.integrations.airtable.record_lookup
python -m examples.integrations.airtable.lead_capture
python -m examples.integrations.airtable.record_update
```

Outbound example:

```bash
python -m examples.integrations.airtable.survey_collection "+15551234567" --name "Dana Park" --record-id "recXXXXXXXXXXXXXX"
```

## Airtable API Reference

- [List Records](https://airtable.com/developers/web/api/list-records)
- [Create Records](https://airtable.com/developers/web/api/create-records)
- [Update Records](https://airtable.com/developers/web/api/update-records)
- [Get Record](https://airtable.com/developers/web/api/get-record)

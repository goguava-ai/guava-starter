# Contact Lookup

**Direction:** Inbound

A customer calls to ask about their account. The agent verifies their identity via email, searches HubSpot for their contact record, and answers questions about their lifecycle stage, company, and other details on file.

## What it does

1. Asks the caller for their email address
2. Searches for a matching contact via `POST /crm/v3/objects/contacts/search`
3. Reads back key properties (lifecycle stage, company, phone, job title) and answers any questions the caller has

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `HUBSPOT_ACCESS_TOKEN` | HubSpot private app access token |

## Usage

```bash
python __main__.py
```

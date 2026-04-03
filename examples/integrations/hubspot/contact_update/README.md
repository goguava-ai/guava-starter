# Contact Update

**Direction:** Inbound

A customer calls to correct or update their contact information on file. The agent verifies their identity via email, collects what needs to change, and patches the HubSpot record.

## What it does

1. Looks up the caller's contact record via `POST /crm/v3/objects/contacts/search`
2. Asks which fields they'd like to update (phone, job title, company, email)
3. Applies changes via `PATCH /crm/v3/objects/contacts/{contactId}`

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `HUBSPOT_ACCESS_TOKEN` | HubSpot private app access token |

## Usage

```bash
python __main__.py
```

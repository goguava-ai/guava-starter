# Contact Update

**Direction:** Inbound

A customer calls to update their contact details on file. The agent verifies their identity by email, captures the field and new value, then patches the Salesforce Contact record in place.

## What it does

1. Greets the caller and asks for their email address to locate their record
2. Queries Salesforce for a matching Contact via `GET /query` (SOQL)
3. Asks which field to update: phone number, job title, mailing address, or email address
4. Applies the change via `PATCH /sobjects/Contact/{id}`

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `SALESFORCE_INSTANCE_URL` | Your Salesforce org URL (e.g. `https://yourorg.my.salesforce.com`) |
| `SALESFORCE_ACCESS_TOKEN` | OAuth2 Bearer token for the Salesforce REST API |

## Usage

```bash
python __main__.py
```

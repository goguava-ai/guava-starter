# Lead Capture

**Direction:** Inbound

A prospect calls and the agent qualifies them with BANT-style questions. Their profile is created or updated as an Intercom lead (role: lead) with custom attributes, then tagged with `inbound-call-lead` and optionally `demo-requested`.

## What it does

1. Searches for existing contact by email via `POST /contacts/search`
2. Creates or updates the contact via `POST /contacts` / `PUT /contacts/{id}` with custom attributes (interest, budget, timeline, lead_source)
3. Applies tags via `POST /tags` and `POST /contacts/{id}/tags`

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `INTERCOM_ACCESS_TOKEN` | Intercom Access Token |

## Usage

```bash
python __main__.py
```

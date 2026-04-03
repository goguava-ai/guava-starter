# Meeting Follow-up

**Direction:** Outbound

After a demo or discovery meeting, the agent calls the contact to check in, answer any remaining questions, and agree on a clear next step. The outcome is logged as a note on the contact record, and the contact's lifecycle stage is advanced if they're moving forward.

## What it does

1. Fetches the contact's company name pre-call via `GET /crm/v3/objects/contacts/{contactId}`
2. Conducts a follow-up conversation: impression, concerns, internal alignment, next step
3. Logs a structured note via `POST /crm/v3/objects/notes`
4. Advances the contact to `opportunity` lifecycle stage if a concrete next step was agreed

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `HUBSPOT_ACCESS_TOKEN` | HubSpot private app access token |

## Usage

```bash
python __main__.py +15551234567 --contact-id 87654321 --name "Jane Smith" --meeting-topic "your product demo"
```

# Win/Loss Survey

**Direction:** Outbound

After a deal closes (won or lost), call the contact to gather structured feedback. The agent adapts its questions based on the outcome, then logs the results as a note associated with both the deal and the contact.

## What it does

1. Fetches the deal name pre-call via `GET /crm/v3/objects/deals/{dealId}`
2. Conducts a win or loss interview depending on `--outcome`
3. Creates a structured note via `POST /crm/v3/objects/notes`, associated with both the deal and the contact

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `HUBSPOT_ACCESS_TOKEN` | HubSpot private app access token |

## Usage

```bash
# Won deal
python __main__.py +15551234567 --deal-id 12345678 --contact-id 87654321 --name "Jane Smith" --outcome won

# Lost deal
python __main__.py +15551234567 --deal-id 12345678 --contact-id 87654321 --name "Jane Smith" --outcome lost
```

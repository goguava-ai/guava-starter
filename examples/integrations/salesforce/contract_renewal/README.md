# Contract Renewal

**Direction:** Outbound

Call customers ahead of contract expiration to confirm renewal intent, capture any requested changes, and advance the Opportunity to the appropriate stage in Salesforce.

## What it does

1. Fetches Opportunity details pre-call via `GET /sobjects/Opportunity/{id}` (name, amount, close date)
2. Reaches the contact and conducts a structured renewal conversation
3. Updates the Opportunity stage via `PATCH /sobjects/Opportunity/{id}`
4. Logs the call as a completed Task via `POST /sobjects/Task`

## Opportunity Stage Mapping

| Intent | Salesforce Stage |
|---|---|
| Renew as-is | `Proposal/Price Quote` |
| Renew with changes | `Value Proposition` |
| Need more time | `Perception Analysis` |
| Not renewing | `Closed Lost` |

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `SALESFORCE_INSTANCE_URL` | Your Salesforce org URL |
| `SALESFORCE_ACCESS_TOKEN` | OAuth2 Bearer token |

## Usage

```bash
python __main__.py +15551234567 --opportunity-id 006... --name "Jane Smith"
```

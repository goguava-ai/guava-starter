# Trial Conversion

**Direction:** Outbound

Calls trial users nearing the end of their Chargebee trial. The agent checks in on their experience, addresses concerns, and converts the subscription to paid immediately if they agree.

## What it does

1. Fetches trial subscription details via `GET /api/v2/subscriptions/{id}`
2. Calls the customer and presents the trial end date and plan pricing
3. Collects their experience and readiness to convert
4. If they agree: ends the trial immediately via `POST /api/v2/subscriptions/{id}/change_term_end`

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `CHARGEBEE_SITE` | Chargebee site subdomain |
| `CHARGEBEE_API_KEY` | Chargebee API key |

## Usage

```bash
python -m examples.integrations.chargebee.trial_conversion "+15551234567" --name "Morgan Blake" --subscription-id "AzZlGKSoMz5b3Bkm1" --trial-end "March 30, 2026"
```

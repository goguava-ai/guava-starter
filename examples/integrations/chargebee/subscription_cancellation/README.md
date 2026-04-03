# Subscription Cancellation

**Direction:** Inbound

A customer calls to cancel their Chargebee subscription. The agent collects their subscription ID, understands their reason, confirms the cancellation, and schedules it for end-of-term via the Chargebee API.

## What it does

1. Collects subscription ID and cancellation reason
2. Fetches subscription details via `GET /api/v2/subscriptions/{id}` to determine end date
3. Cancels the subscription at end of term via `POST /api/v2/subscriptions/{id}/cancel` with `end_of_term=true`
4. Reads back the access end date to the customer

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `CHARGEBEE_SITE` | Chargebee site subdomain |
| `CHARGEBEE_API_KEY` | Chargebee API key |

## Usage

```bash
python -m examples.integrations.chargebee.subscription_cancellation
```

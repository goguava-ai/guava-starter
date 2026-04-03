# Subscription Inquiry

**Direction:** Inbound

A customer calls to check on their Chargebee subscription — plan, billing amount, and next renewal date. The agent verifies their identity and looks up the subscription via the Chargebee API.

## What it does

1. Collects email and subscription ID from the caller
2. Fetches subscription details via `GET /api/v2/subscriptions/{id}`
3. Fetches customer name via `GET /api/v2/customers/{id}`
4. Reads back plan, status, billing amount, renewal date, and cancellation status

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `CHARGEBEE_SITE` | Chargebee site subdomain |
| `CHARGEBEE_API_KEY` | Chargebee API key |

## Usage

```bash
python -m examples.integrations.chargebee.subscription_inquiry
```

# Subscription Cancellation

**Direction:** Inbound

A customer calls to cancel their subscription. The agent verifies their identity, understands their reason for leaving, confirms they want to proceed, and sets `cancel_at_period_end=true` in Stripe so access continues through the end of the billing period.

## What it does

1. Looks up the customer via `GET /v1/customers/search`
2. Retrieves active subscriptions via `GET /v1/subscriptions?customer=...&status=active`
3. Captures cancellation reason and maps it to Stripe's `cancellation_details[feedback]` enum
4. Sets `cancel_at_period_end=true` via `POST /v1/subscriptions/{id}`

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `STRIPE_SECRET_KEY` | Stripe secret API key |

## Usage

```bash
python __main__.py
```

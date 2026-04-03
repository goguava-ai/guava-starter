# Subscription Inquiry

**Direction:** Inbound

A customer calls to check on their subscription. The agent verifies their identity via email, looks up their Stripe account, and answers questions about plan name, billing amount, renewal date, and cancellation status.

## What it does

1. Searches for the customer via `GET /v1/customers/search`
2. Lists their subscriptions via `GET /v1/subscriptions?customer=...&status=active`
3. Falls back to `trialing` and `past_due` if no active subscription is found
4. Reads back plan name, billing amount, status, and next renewal date

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `STRIPE_SECRET_KEY` | Stripe secret API key |

## Usage

```bash
python __main__.py
```

# Plan Upgrade

**Direction:** Inbound

A customer calls to move to a higher-tier plan. The agent looks up their account, confirms the upgrade, and immediately swaps the subscription price in Stripe with prorated billing.

## What it does

1. Looks up the customer via `GET /v1/customers/search`
2. Retrieves active subscriptions via `GET /v1/subscriptions?customer=...&status=active`
3. Swaps the subscription item to the new price via `POST /v1/subscriptions/{id}` with `proration_behavior=create_prorations`

## Configuration

Set environment variables for each plan's Stripe Price ID:

| Variable | Description |
|---|---|
| `STRIPE_PRICE_STARTER` | Price ID for the Starter plan (e.g. `price_xxx`) |
| `STRIPE_PRICE_PROFESSIONAL` | Price ID for the Professional plan |
| `STRIPE_PRICE_ENTERPRISE` | Price ID for the Enterprise plan |

Only plans with a configured Price ID will be offered as choices to the caller.

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `STRIPE_SECRET_KEY` | Stripe secret API key |

## Usage

```bash
STRIPE_PRICE_PROFESSIONAL=price_xxx python __main__.py
```

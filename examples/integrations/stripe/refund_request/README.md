# Refund Request

**Direction:** Inbound

A customer calls to request a refund. The agent verifies their identity, captures the reason, finds the most recent eligible charge on their account, and issues a full refund via the Stripe API.

## What it does

1. Looks up the customer via `GET /v1/customers/search`
2. Lists recent succeeded charges via `GET /v1/charges?customer=...&limit=5`
3. Filters to non-refunded succeeded charges
4. Creates a refund via `POST /v1/refunds` with the appropriate Stripe reason code

## Reason Mapping

| Spoken reason | Stripe `reason` value |
|---|---|
| Duplicate charge | `duplicate` |
| Fraudulent charge | `fraudulent` |
| Other | `requested_by_customer` |

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `STRIPE_SECRET_KEY` | Stripe secret API key |

## Usage

```bash
python __main__.py
```

# Churn Winback

**Direction:** Outbound

Call recently canceled customers to gather honest feedback and gauge their interest in returning. If they're interested, a win-back coupon is attached to their account so it automatically applies when they resubscribe.

## What it does

1. Fetches the canceled subscription pre-call via `GET /v1/subscriptions?customer=...&status=canceled`
2. Conducts a brief exit interview: cancellation reason, competitor info, what would bring them back
3. Records outcome in customer metadata via `POST /v1/customers/{id}`
4. If the customer is interested in returning and `STRIPE_WINBACK_COUPON_ID` is set, attaches the coupon via `POST /v1/customers/{id}` with `coupon=...`

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `STRIPE_SECRET_KEY` | Stripe secret API key |
| `STRIPE_WINBACK_COUPON_ID` | (Optional) Coupon ID to attach for interested customers |

## Usage

```bash
python __main__.py +15551234567 --customer-id cus_abc123 --name "Jane Smith"
```

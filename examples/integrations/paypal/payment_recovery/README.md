# Payment Recovery

**Direction:** Outbound

Calls customers with failed PayPal subscription payments to explain the issue and guide them to update their payment method in PayPal.

## What it does

1. Fetches subscription details via `GET /v1/billing/subscriptions/{subscriptionId}` (failed_payments_count, last_payment)
2. Calls the customer and explains the payment failure
3. Collects the root cause and their willingness to update their payment method
4. Provides step-by-step PayPal payment update instructions if they need help

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `PAYPAL_CLIENT_ID` | PayPal REST API client ID |
| `PAYPAL_CLIENT_SECRET` | PayPal REST API client secret |
| `PAYPAL_BASE_URL` | `https://api-m.sandbox.paypal.com` or `https://api-m.paypal.com` |

## Usage

```bash
python -m examples.integrations.paypal.payment_recovery "+15551234567" --name "Jordan Lee" --subscription-id "I-BW452GLLEP1G"
```

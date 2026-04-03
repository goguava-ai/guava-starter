# Payment Recovery

**Direction:** Outbound

Calls customers with dunning Chargebee subscriptions to understand why payment failed and retry the charge if they've updated their payment method.

## What it does

1. Fetches subscription details via `GET /api/v2/subscriptions/{id}` (total_dues, due_invoices_count)
2. Calls the customer and explains the outstanding balance
3. Collects the root cause and their willingness to retry payment
4. If they've updated their payment method: retries via `POST /api/v2/subscriptions/{id}/collect_now`

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `CHARGEBEE_SITE` | Chargebee site subdomain |
| `CHARGEBEE_API_KEY` | Chargebee API key |

## Usage

```bash
python -m examples.integrations.chargebee.payment_recovery "+15551234567" --name "Morgan Blake" --subscription-id "AzZlGKSoMz5b3Bkm1"
```

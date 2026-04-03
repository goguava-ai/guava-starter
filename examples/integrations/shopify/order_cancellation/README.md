# Order Cancellation

**Direction:** Inbound

A customer calls to cancel a Shopify order. The agent verifies their email, looks up the open order, confirms the cancellation with the customer, and cancels it with restocking and a confirmation email.

## What it does

1. Collects customer email and optional order number
2. Searches orders via `GET /admin/api/2026-01/orders.json?email=...&status=open`
3. Confirms cancellation with the customer
4. Cancels via `POST /admin/api/2026-01/orders/{id}/cancel.json` with `email: true` and `restock: true`

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `SHOPIFY_STORE` | Shopify store subdomain |
| `SHOPIFY_ACCESS_TOKEN` | Admin API access token |

## Usage

```bash
python -m examples.integrations.shopify.order_cancellation
```

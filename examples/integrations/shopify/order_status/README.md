# Order Status

**Direction:** Inbound

A customer calls to check the status of a Shopify order. The agent verifies their email, looks up recent orders, and reads back fulfillment status, financial status, and tracking information.

## What it does

1. Collects customer email and optional order number
2. Searches orders via `GET /admin/api/2026-01/orders.json?email=...`
3. Filters by order number if provided
4. Reads back fulfillment status, payment status, total price, and tracking numbers from fulfillments

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `SHOPIFY_STORE` | Shopify store subdomain |
| `SHOPIFY_ACCESS_TOKEN` | Admin API access token |

## Usage

```bash
python -m examples.integrations.shopify.order_status
```

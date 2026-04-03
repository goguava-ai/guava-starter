# Shipping Update

**Direction:** Outbound

An outbound call is placed to a customer to share a shipping update on their Shopify order. The agent loads the order's fulfillment and tracking information, delivers the update, and handles any delivery issues the customer reports.

## What it does

1. Loads the order and fulfillment tracking via `GET /admin/api/2026-01/orders/{id}.json`
2. Extracts tracking company, tracking numbers, and shipment status from fulfillments
3. Calls the customer, delivers the update, and logs any reported issues

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `SHOPIFY_STORE` | Shopify store subdomain |
| `SHOPIFY_ACCESS_TOKEN` | Admin API access token |

## Usage

```bash
python -m examples.integrations.shopify.shipping_update \
  --order-id 5678901234 \
  --customer-name "Jamie" \
  --phone "+15551234567"
```

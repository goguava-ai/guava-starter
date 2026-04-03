# Return Request

**Direction:** Inbound

A customer calls to return an item from a Shopify order. The agent collects the order details, return reason, and item description, then creates a return with a customer notification.

## What it does

1. Collects customer email, order number, return reason, and item description
2. Finds the order via `GET /admin/api/2026-01/orders.json?email=...`
3. Matches the described item to a line item in the order
4. Creates a return via `POST /admin/api/2026-01/returns.json` with `notify_customer: true`

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `SHOPIFY_STORE` | Shopify store subdomain |
| `SHOPIFY_ACCESS_TOKEN` | Admin API access token |

## Usage

```bash
python -m examples.integrations.shopify.return_request
```

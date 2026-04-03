# Order Status

**Direction:** Inbound

A customer calls Harbor House to find out where their order is. The agent collects their email and optional order number, looks up their order in BigCommerce in real time, reads back the status, items, and total, then asks what they'd like to do next.

## What it does

1. Accepts the inbound call and greets the customer as Jordan from Harbor House.
2. Collects the customer's email address and, optionally, their order number.
3. Queries `GET /v2/orders?email=<email>&sort=date_created:desc&limit=5` to retrieve recent orders.
4. Matches the specific order number if provided, or falls back to the most recent order.
5. Fetches line items via `GET /v2/orders/{id}/products` and builds a readable item summary.
6. Reads back the order ID, placed date, status (mapped to a friendly label), item list, and total.
7. Asks the customer what they'd like to do next: track shipment, cancel, speak to someone, or end the call.
8. Routes to the appropriate hangup instructions based on their choice.

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `BIGCOMMERCE_STORE_HASH` | Your BigCommerce store hash (from the store URL) |
| `BIGCOMMERCE_AUTH_TOKEN` | API access token from the BigCommerce control panel |

## Usage

```bash
export GUAVA_AGENT_NUMBER="+1..."
export BIGCOMMERCE_STORE_HASH="abc123"
export BIGCOMMERCE_AUTH_TOKEN="your_token_here"

python -m examples.integrations.bigcommerce.order_status
```

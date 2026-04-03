# Order Status Inquiry

**Direction:** Inbound

Customer calls to check on their order status; the agent looks up their most recent order by email address and reads back the current status, carrier, and tracking number.

## What it does

1. Answers the inbound call and greets the caller as Sierra from Crestline Outdoor Gear.
2. Collects the caller's email address.
3. Looks up the customer via `GET /v3/customers?email:in={email}`.
4. Fetches their most recent order via `GET /v2/orders?customer_id={id}&limit=1&sort=id:desc`.
5. Fetches shipment and tracking info via `GET /v2/orders/{id}/shipments`.
6. Reads back the order status, carrier, and tracking number (if available).

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `BIGCOMMERCE_STORE_HASH` | Your BigCommerce store hash (from the store URL) |
| `BIGCOMMERCE_ACCESS_TOKEN` | API access token from BigCommerce Advanced Settings → API Accounts |

## Usage

```bash
export GUAVA_AGENT_NUMBER="+15551234567"
export BIGCOMMERCE_STORE_HASH="abc123"
export BIGCOMMERCE_ACCESS_TOKEN="your_token_here"

python __main__.py
```

# Order Status

**Direction:** Inbound

A customer calls to check the status of a Square order. The agent collects their order ID and looks it up via the Square Orders API, reading back the order state, fulfillment status, and tracking information.

## What it does

1. Collects order ID from the caller
2. Fetches order details via `GET /v2/orders/{orderId}`
3. Reads back order state (`OPEN`, `COMPLETED`, `CANCELED`), fulfillment state, and tracking number if available

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `SQUARE_ACCESS_TOKEN` | Square access token |
| `SQUARE_BASE_URL` | `https://connect.squareupsandbox.com` or `https://connect.squareup.com` |

## Usage

```bash
python -m examples.integrations.square.order_status
```

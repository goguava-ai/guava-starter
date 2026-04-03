# Order Status

**Direction:** Inbound

A customer calls to check the status of a PayPal order. The agent verifies their email, collects the order ID, and looks it up via the PayPal Orders v2 API.

## What it does

1. Obtains a Bearer token via `POST /v1/oauth2/token` (client credentials)
2. Looks up the order via `GET /v2/checkout/orders/{orderId}`
3. Reads back the order status, total amount, and creation date

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `PAYPAL_CLIENT_ID` | PayPal REST API client ID |
| `PAYPAL_CLIENT_SECRET` | PayPal REST API client secret |
| `PAYPAL_BASE_URL` | `https://api-m.sandbox.paypal.com` or `https://api-m.paypal.com` |

## Usage

```bash
python -m examples.integrations.paypal.order_status
```

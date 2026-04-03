# Refund Request

**Direction:** Inbound

A customer calls to request a refund on a completed PayPal order. The agent collects the order ID, verifies the order status and capture ID, and initiates a full refund via the PayPal Payments API.

## What it does

1. Collects order ID and refund reason from the caller
2. Fetches order details via `GET /v2/checkout/orders/{orderId}`
3. Extracts the capture ID from the order's completed payments
4. Creates a refund via `POST /v2/payments/captures/{captureId}/refund`

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `PAYPAL_CLIENT_ID` | PayPal REST API client ID |
| `PAYPAL_CLIENT_SECRET` | PayPal REST API client secret |
| `PAYPAL_BASE_URL` | `https://api-m.sandbox.paypal.com` or `https://api-m.paypal.com` |

## Usage

```bash
python -m examples.integrations.paypal.refund_request
```

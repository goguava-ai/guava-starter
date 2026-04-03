# Refund Request

**Direction:** Inbound

A customer calls to request a refund on a Square payment. The agent collects the payment ID, verifies the payment status, and creates a refund via the Square Refunds API.

## What it does

1. Collects payment ID and refund reason from the caller
2. Fetches payment details via `GET /v2/payments/{paymentId}`
3. Verifies the payment is in `COMPLETED` status before proceeding
4. Creates a full refund via `POST /v2/refunds` with an idempotency key

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `SQUARE_ACCESS_TOKEN` | Square access token |
| `SQUARE_BASE_URL` | `https://connect.squareupsandbox.com` or `https://connect.squareup.com` |

## Usage

```bash
python -m examples.integrations.square.refund_request
```

# Refund Request

**Direction:** Inbound

Customer calls to request a refund; the agent verifies the order exists and is in a refundable state, then posts the refund to the BigCommerce API.

## What it does

1. Answers the inbound call and greets the caller as Sierra from Crestline Outdoor Gear.
2. Collects the order number and the reason for the refund (multiple choice).
3. Verifies the order exists via `GET /v2/orders/{id}` and returns a 404-aware error message if not found.
4. Checks that the order's `status_id` is eligible for a refund (Shipped, Partially Shipped, Awaiting Shipment, Completed, or Awaiting Fulfillment).
5. Fetches line items via `GET /v2/orders/{id}/products` to build the refund payload.
6. Submits the refund via `POST /v2/orders/{id}/refunds` with all line items and the customer-provided reason.
7. Confirms the outcome to the caller — success with expected timeline, or a graceful fallback if the API call fails.

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

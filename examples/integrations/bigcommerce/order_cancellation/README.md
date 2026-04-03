# Order Cancellation

**Direction:** Inbound

A customer calls Harbor House to cancel an order. The agent collects their email, order number, and reason, verifies the order in BigCommerce, checks whether it's still cancellable, confirms intent with the customer, and — if confirmed — applies the cancellation via the BigCommerce API.

## What it does

1. Accepts the inbound call and greets the customer as Morgan from Harbor House.
2. Collects the customer's email address, order number, and cancellation reason (multiple choice).
3. Queries `GET /v2/orders?email=<email>` to verify the order exists under that email address.
4. Checks the order's `status_id` against the set of cancellable statuses (`0`, `1`, `7`, `9`, `11` — states where the order has not yet shipped or been completed).
5. If the order cannot be cancelled (already shipped, completed, etc.), ends the call with instructions to initiate a return instead.
6. If cancellable, asks the customer to confirm they want to proceed.
7. On confirmation, calls `PUT /v2/orders/{id}` with `{"status_id": 5}` (Cancelled) and appends the reason to `staff_notes`.
8. Confirms cancellation to the customer and advises on refund timeline.

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

python -m examples.integrations.bigcommerce.order_cancellation
```

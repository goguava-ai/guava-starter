# Order Cancellation — Magento / Adobe Commerce Integration

An inbound voice agent that helps customers cancel orders that haven't yet been delivered. The agent verifies the order, checks eligibility for cancellation, confirms intent with the customer, and then calls the Magento cancel endpoint.

## How It Works

**1. Collect order and reason**

The agent gathers the order number, the customer's name for identity verification, and their reason for canceling.

**2. Check cancellation eligibility**

`get_order_by_increment_id()` fetches the order. Orders in `complete`, `closed`, or `canceled` status are immediately ineligible. Orders in `processing` may already be in fulfillment — the cancel is attempted but the customer is warned.

**3. Confirm before canceling**

A second `set_task()` reads back the order total and asks for explicit confirmation before proceeding. This prevents accidental cancellations.

**4. Execute the cancellation**

`cancel_order()` calls `POST /rest/V1/orders/{id}/cancel`. On success, the customer is told to expect a 5–7 day refund. On failure, the case is escalated to customer service.

## Magento API Calls

| Timing | Method | Endpoint | Purpose |
|---|---|---|---|
| Mid-call | `GET` | `/rest/V1/orders` | Fetch order by increment ID |
| Post-confirm | `POST` | `/rest/V1/orders/{id}/cancel` | Cancel the order |

## Setup

```bash
export GUAVA_AGENT_NUMBER="+1..."
export MAGENTO_BASE_URL="https://mystore.com"
export MAGENTO_ACCESS_TOKEN="..."
```

## Run

```bash
python -m examples.integrations.magento.order_cancellation
```

## Sample Output

```json
{
  "use_case": "order_cancellation",
  "order_number": "000001234",
  "caller_name": "Jane Doe",
  "cancel_reason": "ordered by mistake",
  "success": true
}
```

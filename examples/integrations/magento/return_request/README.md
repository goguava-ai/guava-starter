# Return Request — Magento / Adobe Commerce Integration

An inbound voice agent that initiates returns and exchanges for customers. The agent collects the order number, return reason, and item condition, then creates an RMA (Return Merchandise Authorization) in Magento.

## How It Works

**1. Collect return details**

The agent gathers the order number, customer name, return type (refund or exchange), item description, reason, and condition.

**2. Look up the order**

`get_order_by_increment_id()` retrieves the order to verify it exists and check its status. Orders in `pending` or `processing` status cannot be returned yet.

**3. Create an RMA**

`create_rma()` posts to `POST /rest/V1/returns` with the order ID, customer name, return reason, and line item references. The RMA is created in `pending` status for the warehouse team to process.

**4. Confirm with the caller**

For refunds, the caller is told to expect a prepaid return label and 5–7 day refund window. For exchanges, a follow-up email is promised.

## Magento API Calls

| Timing | Method | Endpoint | Purpose |
|---|---|---|---|
| Mid-call | `GET` | `/rest/V1/orders` | Look up order by increment ID |
| Post-confirm | `POST` | `/rest/V1/returns` | Create RMA for the order |

## Setup

```bash
export GUAVA_AGENT_NUMBER="+1..."
export MAGENTO_BASE_URL="https://mystore.com"
export MAGENTO_ACCESS_TOKEN="..."
```

## Run

```bash
python -m examples.integrations.magento.return_request
```

## Sample Output

```json
{
  "use_case": "return_request",
  "order_number": "000001234",
  "customer_name": "Jane Doe",
  "return_type": "return for refund",
  "item_description": "Ceramic serving bowl set",
  "return_reason": "defective or damaged",
  "rma_id": "R000000001"
}
```

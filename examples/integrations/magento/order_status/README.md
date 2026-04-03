# Order Status — Magento / Adobe Commerce Integration

An inbound voice agent that allows customers to check their order status. Callers can look up by order number or by the email address on their account.

## How It Works

**1. Collect the lookup preference**

The agent asks whether the caller has an order number or prefers to search by email.

**2. Query the Magento Orders API**

- By order number: `GET /rest/V1/orders?searchCriteria[...][increment_id]=eq:{id}`
- By email: `GET /rest/V1/orders?searchCriteria[...][customer_email]=eq:{email}&$orderby=created_at desc`

**3. Map status to plain language**

`format_order()` translates Magento status codes to conversational descriptions:
- `pending` → "we've received your order and are preparing it"
- `processing` → "being prepared for shipment"
- `complete` → "delivered"

**4. Present the result**

For a specific order, detailed status and shipping method are read. For account lookups, up to 3 recent orders are summarized.

## Magento API Calls

| Timing | Method | Endpoint | Purpose |
|---|---|---|---|
| Mid-call | `GET` | `/rest/V1/orders` | Search orders by order number or customer email |

## Setup

```bash
export GUAVA_AGENT_NUMBER="+1..."
export MAGENTO_BASE_URL="https://mystore.com"
export MAGENTO_ACCESS_TOKEN="..."
```

## Run

```bash
python -m examples.integrations.magento.order_status
```

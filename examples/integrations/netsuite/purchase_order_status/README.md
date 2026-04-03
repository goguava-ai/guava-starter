# Purchase Order Status — NetSuite Integration

An inbound voice agent that allows vendors and procurement staff to check the status of purchase orders in NetSuite by PO number or vendor name.

## How It Works

**1. Collect lookup preference**

The agent asks whether the caller has a specific PO number or would like to search by vendor name.

**2. Query NetSuite**

- By PO number: `GET /purchaseOrder?q=tranid IS {number}` then fetches the full record with `expandSubResources=true` to include line items
- By vendor: `GET /purchaseOrder?q=vendor.entityid CONTAINS {name} AND status IS Open`

**3. Parse and present results**

`format_po_summary()` reads status, total, currency, and expected date. For specific POs, the number of received line items is also reported.

## NetSuite API Calls

| Timing | Method | Endpoint | Purpose |
|---|---|---|---|
| Mid-call | `GET` | `/purchaseOrder?q=tranid IS {n}` | Search PO by transaction number |
| Mid-call | `GET` | `/purchaseOrder/{id}?expandSubResources=true` | Fetch PO with line items |
| Mid-call | `GET` | `/purchaseOrder?q=vendor.entityid CONTAINS {n}` | Search open POs by vendor |

## Setup

```bash
export GUAVA_AGENT_NUMBER="+1..."
export NETSUITE_ACCOUNT_ID="1234567"
export NETSUITE_CONSUMER_KEY="..."
export NETSUITE_CONSUMER_SECRET="..."
export NETSUITE_TOKEN_KEY="..."
export NETSUITE_TOKEN_SECRET="..."
```

## Run

```bash
python -m examples.integrations.netsuite.purchase_order_status
```

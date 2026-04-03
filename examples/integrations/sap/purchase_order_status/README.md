# Purchase Order Status — SAP S/4HANA Integration

An inbound voice agent for vendors and procurement staff checking the status of purchase orders. Callers can look up a specific PO by number, or see all open POs associated with their vendor account.

## How It Works

**1. Determine lookup method**

The agent asks whether the caller has a specific PO number or a vendor account number.

**2. Query the SAP Purchase Order OData API**

- By PO: `GET /A_PurchaseOrder('{id}')` with `$expand=to_PurchaseOrderItem`
- By vendor: `GET /A_PurchaseOrder?$filter=Supplier eq '{id}' and PurchaseOrderStatus eq 'B'`

**3. Present the results**

`format_po_summary()` maps the `PurchaseOrderStatus` field (`A`=open, `B`=in process, `C`=closed) and reads the result including the scheduled delivery date if available.

## SAP API Calls

| Timing | Method | Endpoint | Purpose |
|---|---|---|---|
| Mid-call | `GET` | `/API_PURCHASEORDER_PROCESS_SRV/A_PurchaseOrder('{id}')` | Fetch PO with line items |
| Mid-call | `GET` | `/API_PURCHASEORDER_PROCESS_SRV/A_PurchaseOrder` | Search open POs by vendor |

## Setup

```bash
export GUAVA_AGENT_NUMBER="+1..."
export SAP_BASE_URL="https://mycompany.s4hana.cloud.sap"
export SAP_CLIENT_ID="..."
export SAP_CLIENT_SECRET="..."
export SAP_TOKEN_URL="https://mycompany.authentication.eu10.hana.ondemand.com/oauth/token"
```

## Run

```bash
python -m examples.integrations.sap.purchase_order_status
```

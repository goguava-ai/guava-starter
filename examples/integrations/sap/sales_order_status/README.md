# Sales Order Status — SAP S/4HANA Integration

An inbound voice agent that allows customers to check the status of their sales orders. Callers can look up a specific order by order number, or retrieve all recent orders by their customer account number.

## How It Works

**1. Collect lookup preference**

The agent asks whether the caller has a specific order number or wants to search by account number.

**2. Query the SAP Sales Order OData API**

- By order ID: `GET /A_SalesOrder('{id}')` with `$expand=to_Item`
- By customer: `GET /A_SalesOrder?$filter=SoldToParty eq '{id}'&$orderby=CreationDate desc&$top=5`

**3. Parse and present results**

`format_order_summary()` maps the `OverallSDProcessStatus` code to a human-readable label (`A`=open, `B`=partially processed, `C`=fully processed) and reads the result to the caller.

## SAP API Calls

| Timing | Method | Endpoint | Purpose |
|---|---|---|---|
| Mid-call | `GET` | `/API_SALES_ORDER_SRV/A_SalesOrder('{id}')` | Fetch specific order with line items |
| Mid-call | `GET` | `/API_SALES_ORDER_SRV/A_SalesOrder` | Search orders by customer account |

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
python -m examples.integrations.sap.sales_order_status
```

## Sample Output

```json
{
  "use_case": "sales_order_status",
  "lookup_type": "specific order number",
  "identifier": "4500000123",
  "orders_found": 1,
  "orders": [
    {
      "SalesOrder": "4500000123",
      "OverallSDProcessStatus": "B",
      "TotalNetAmount": "8750.00",
      "TransactionCurrency": "USD",
      "CreationDate": "2026-03-10"
    }
  ]
}
```

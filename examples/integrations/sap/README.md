# SAP S/4HANA Cloud Integration

Voice agents that integrate with the [SAP S/4HANA Cloud OData APIs](https://api.sap.com) to look up sales orders, handle invoice inquiries, track purchase orders, and follow up on overdue payments — all over the phone.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`sales_order_status`](sales_order_status/) | Inbound | Customer calls to check sales order status by order number or account |
| [`invoice_inquiry`](invoice_inquiry/) | Inbound | Customer calls with a question or dispute about an invoice; concern is logged in SAP |
| [`purchase_order_status`](purchase_order_status/) | Inbound | Vendor or procurement staff checks PO status by PO number or vendor account |
| [`overdue_invoice_followup`](overdue_invoice_followup/) | Outbound | Agent calls customers with overdue invoices to confirm payment status and logs outcome |

## Authentication

All examples use OAuth 2.0 client credentials via SAP's XSUAA service:

```
POST {SAP_TOKEN_URL}
Content-Type: application/x-www-form-urlencoded
Authorization: Basic base64("{client_id}:{client_secret}")
grant_type=client_credentials
→ {"access_token": "..."}
```

The token is passed as `Authorization: Bearer {token}` on OData API calls.

## Common Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `SAP_BASE_URL` | Your S/4HANA Cloud tenant URL (e.g. `https://mycompany.s4hana.cloud.sap`) |
| `SAP_CLIENT_ID` | OAuth client ID from SAP BTP service key |
| `SAP_CLIENT_SECRET` | OAuth client secret |
| `SAP_TOKEN_URL` | XSUAA token URL from SAP BTP service key |

## SAP OData APIs Used

| API | Path |
|---|---|
| Sales Order | `/sap/opu/odata/sap/API_SALES_ORDER_SRV/A_SalesOrder` |
| Billing Document | `/sap/opu/odata/sap/API_BILLING_DOCUMENT_SRV/A_BillingDocument` |
| Purchase Order | `/sap/opu/odata/sap/API_PURCHASEORDER_PROCESS_SRV/A_PurchaseOrder` |

## SAP API Reference

- [API Sales Order SRV](https://api.sap.com/api/API_SALES_ORDER_SRV/overview)
- [API Billing Document SRV](https://api.sap.com/api/API_BILLING_DOCUMENT_SRV/overview)
- [API Purchase Order Process SRV](https://api.sap.com/api/API_PURCHASEORDER_PROCESS_SRV/overview)
- [API Business Partner](https://api.sap.com/api/API_BUSINESS_PARTNER/overview)

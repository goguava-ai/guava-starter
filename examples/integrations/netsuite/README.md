# NetSuite Integration

Voice agents that integrate with the [NetSuite SuiteTalk REST API](https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/chapter_156256948326.html) to handle invoice inquiries, collect payments, look up customer accounts, and track purchase orders — all over the phone.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`invoice_inquiry`](invoice_inquiry/) | Inbound | Customer calls to check invoice status, balance, or dispute a charge |
| [`payment_collection`](payment_collection/) | Outbound | Agent calls customer about an overdue invoice and logs the outcome in NetSuite |
| [`customer_account_lookup`](customer_account_lookup/) | Inbound | Customer calls to check account balance, credit limit, open invoices, or payment terms |
| [`purchase_order_status`](purchase_order_status/) | Inbound | Vendor or procurement staff checks PO status by PO number or vendor name |

## Authentication

All examples use NetSuite Token-Based Authentication (TBA) via OAuth 1.0a with HMAC-SHA256. Install `requests-oauthlib` to use the `OAuth1` helper:

```bash
pip install requests-oauthlib
```

TBA credentials are generated in NetSuite: **Setup** → **Users/Roles** → **Access Tokens** → **New Access Token**.

## Common Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `NETSUITE_ACCOUNT_ID` | Your NetSuite account ID (e.g. `1234567`) |
| `NETSUITE_CONSUMER_KEY` | TBA consumer key |
| `NETSUITE_CONSUMER_SECRET` | TBA consumer secret |
| `NETSUITE_TOKEN_KEY` | TBA token key |
| `NETSUITE_TOKEN_SECRET` | TBA token secret |

## NetSuite REST Record API

Base URL format:
```
https://{account_id}.suitetalk.api.netsuite.com/services/rest/record/v1/
```

| Resource | Endpoint |
|---|---|
| Invoice | `/invoice`, `/invoice/{id}` |
| Customer | `/customer`, `/customer/{id}` |
| Customer Payment | `/customerPayment` |
| Purchase Order | `/purchaseOrder`, `/purchaseOrder/{id}` |

## NetSuite API Reference

- [REST Record API Overview](https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/chapter_156256948326.html)
- [SuiteTalk REST Web Services](https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/book_1559132836.html)
- [Token-Based Authentication](https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_4247337262.html)

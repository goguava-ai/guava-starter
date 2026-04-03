# Invoice Inquiry — SAP S/4HANA Integration

An inbound voice agent for customers calling with questions or disputes about invoices. The agent looks up the billing document in SAP, confirms the amount and status, and logs a dispute note against the document for the AR team to follow up.

## How It Works

**1. Collect invoice details and concern**

The agent gathers the invoice number, caller name, type of concern (incorrect amount, already paid, missing item, need a copy, other), and optional detail.

**2. Fetch the billing document from SAP**

`get_billing_document()` calls `GET /A_BillingDocument('{id}')` to retrieve the document with line items. A 404 response is handled gracefully.

**3. Log the dispute**

For non-informational concerns, `create_dispute_note()` writes a brief note to the billing document header using a PATCH (`X-HTTP-Method: MERGE`) call, allowing the AR team to see call outcomes in SAP.

**4. Respond to the caller**

The agent confirms the invoice amount and date and either tells the caller a copy will be resent or lets them know the dispute has been logged and AR will follow up within two business days.

## SAP API Calls

| Timing | Method | Endpoint | Purpose |
|---|---|---|---|
| Mid-call | `GET` | `/API_BILLING_DOCUMENT_SRV/A_BillingDocument('{id}')` | Fetch invoice details |
| Post-call | `POST` (MERGE) | `/API_BILLING_DOCUMENT_SRV/A_BillingDocument('{id}')` | Write dispute note to document |

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
python -m examples.integrations.sap.invoice_inquiry
```

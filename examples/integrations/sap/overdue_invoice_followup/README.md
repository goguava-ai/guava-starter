# Overdue Invoice Follow-up — SAP S/4HANA Integration

An outbound voice agent that calls customers about overdue invoices. The agent confirms whether the invoice was received, gathers the expected payment timeline, and records the outcome back to the SAP billing document.

## How It Works

**1. Initiate an outbound call with invoice context**

Invoice details (ID, amount, currency, due date) are passed via CLI arguments and loaded before the call begins.

**2. Reach the contact**

`reach_person()` ensures the agent is speaking with the correct contact before proceeding with sensitive financial discussion.

**3. Capture payment intent**

The agent asks whether the invoice was received and gathers the payment status: already sent, expected timeline, dispute, or hardship.

**4. Record the dunning outcome in SAP**

`update_billing_document_status()` writes a brief dunning note (`Dunning call YYYYMMDD: {outcome}`) to the billing document header using a PATCH call.

**5. Close appropriately**

The agent's closing message adapts to each payment status — confirming expected timelines, acknowledging disputes, or flagging hardship cases for specialist follow-up.

## SAP API Calls

| Timing | Method | Endpoint | Purpose |
|---|---|---|---|
| Post-call | `POST` (MERGE) | `/API_BILLING_DOCUMENT_SRV/A_BillingDocument('{id}')` | Write dunning call outcome |

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
python -m examples.integrations.sap.overdue_invoice_followup \
  +15551234567 \
  --name "Jane Smith" \
  --invoice-id "9000000456" \
  --amount "4250.00" \
  --currency "USD" \
  --due-date "2026-03-01"
```

## Sample Output

```json
{
  "use_case": "overdue_invoice_followup",
  "contact": "Jane Smith",
  "invoice_id": "9000000456",
  "invoice_amount": "4250.00 USD",
  "due_date": "2026-03-01",
  "invoice_received": "yes",
  "payment_status": "will pay within 7 days",
  "payment_notes": "wire transfer in progress"
}
```

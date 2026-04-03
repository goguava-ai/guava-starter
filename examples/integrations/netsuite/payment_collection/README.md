# Payment Collection — NetSuite Integration

An outbound voice agent that calls customers about overdue invoices, gathers payment intent, and records the outcome back to the invoice in NetSuite.

## How It Works

**1. Initiate with invoice context**

Invoice details are passed as CLI arguments. `reach_person()` ensures the right contact is reached.

**2. Gather payment intent**

The agent explains the overdue invoice and captures the customer's payment status: already sent, paying now by card, committing to a timeline, disputing, or requesting a payment plan.

**3. Record the outcome in NetSuite**

`add_invoice_memo()` patches the invoice's `memo` field with a dated collection call note (e.g. `Collection call 2026-03-31: will pay within 7 days`).

**4. Adapt the closing**

Each payment status gets a tailored response — confirming timelines, arranging card transfer, acknowledging disputes, or promising payment plan outreach.

## NetSuite API Calls

| Timing | Method | Endpoint | Purpose |
|---|---|---|---|
| Post-call | `PATCH` | `/invoice/{id}` | Write collection outcome to invoice memo |

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
python -m examples.integrations.netsuite.payment_collection \
  +15551234567 \
  --name "Jane Smith" \
  --customer-id "456" \
  --invoice-id "789" \
  --invoice-number "INV-2026-0042" \
  --amount "3200.00" \
  --currency "USD" \
  --due-date "2026-02-28"
```

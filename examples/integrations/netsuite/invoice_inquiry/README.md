# Invoice Inquiry — NetSuite Integration

An inbound voice agent that helps customers look up their invoices in NetSuite. Callers can search by invoice number or email address and get their balance, status, or dispute logged.

## How It Works

**1. Collect lookup preference and question type**

The agent asks whether the caller has an invoice number or email, and what specifically they need (balance, payment status, dispute, copy).

**2. Query the NetSuite REST Record API**

- By invoice number: `GET /invoice?q=tranid IS {number}` then `GET /invoice/{id}`
- By email: `GET /invoice?q=email IS {email}`

**3. Respond based on inquiry type**

- Balance due: reads amount remaining and due date
- Payment status: reads status and balance
- Dispute: acknowledges and promises AR follow-up
- Copy: promises email delivery within one business day

## NetSuite API Calls

| Timing | Method | Endpoint | Purpose |
|---|---|---|---|
| Mid-call | `GET` | `/invoice?q=tranid IS {n}` | Search invoice by transaction number |
| Mid-call | `GET` | `/invoice/{id}` | Fetch full invoice record |
| Mid-call | `GET` | `/invoice?q=email IS {email}` | Search invoices by customer email |

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
python -m examples.integrations.netsuite.invoice_inquiry
```

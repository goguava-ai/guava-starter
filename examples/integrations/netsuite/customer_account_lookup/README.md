# Customer Account Lookup — NetSuite Integration

An inbound voice agent that allows customers to check their NetSuite account details by email — including account balance, credit limit, open invoices, and payment terms.

## How It Works

**1. Collect email and question type**

The agent asks for the email address on file and what the caller specifically needs.

**2. Look up the customer record**

`find_customer_by_email()` queries `GET /customer?q=email IS {email}`, then fetches the full record with `GET /customer/{id}`.

**3. Serve the specific need**

- Balance / credit limit: reads from `balance` and `creditlimit` fields
- Open invoices: runs `GET /invoice?q=customer.id IS {id} AND status IS Open` and summarizes
- Contact info: reads phone and default address
- Payment terms: reads the `terms` reference field

## NetSuite API Calls

| Timing | Method | Endpoint | Purpose |
|---|---|---|---|
| Mid-call | `GET` | `/customer?q=email IS {email}` | Find customer by email |
| Mid-call | `GET` | `/customer/{id}` | Fetch full customer record |
| Mid-call (optional) | `GET` | `/invoice?q=customer.id IS {id} AND status IS Open` | Fetch open invoices |

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
python -m examples.integrations.netsuite.customer_account_lookup
```

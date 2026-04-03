# Billing Inquiry

**Direction:** Inbound

A customer calls with a billing question. The agent verifies their identity by email, retrieves recent invoices from the `invoices` table, and addresses common topics such as invoice amounts, unrecognized charges, refund requests, and payment method updates.

## Expected Schema

```sql
CREATE TABLE accounts (
    id     SERIAL PRIMARY KEY,
    name   TEXT,
    plan   TEXT,
    status TEXT DEFAULT 'active'
);

CREATE TABLE users (
    id         SERIAL PRIMARY KEY,
    account_id INT REFERENCES accounts(id),
    email      TEXT UNIQUE,
    full_name  TEXT,
    role       TEXT DEFAULT 'member'
);

CREATE TABLE invoices (
    id             SERIAL PRIMARY KEY,
    account_id     INT REFERENCES accounts(id),
    invoice_number TEXT UNIQUE,
    amount         NUMERIC(10,2),
    currency       TEXT DEFAULT 'USD',
    status         TEXT,          -- e.g. 'paid', 'pending', 'overdue'
    period_start   DATE,
    period_end     DATE,
    due_date       DATE,
    paid_at        TIMESTAMPTZ,
    created_at     TIMESTAMPTZ DEFAULT NOW()
);
```

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `PGHOST` | PostgreSQL hostname |
| `PGUSER` | PostgreSQL username |
| `PGPASSWORD` | PostgreSQL password |
| `PGDATABASE` | Database name |

## Usage

```bash
python __main__.py
```

# Account Lookup

**Direction:** Inbound

A SaaS customer calls to check their account plan, seat count, API usage, and renewal date. The agent verifies their identity by email and reads back their account details from the database.

## Expected Schema

```sql
CREATE TABLE accounts (
    id                    SERIAL PRIMARY KEY,
    name                  TEXT,
    plan                  TEXT,                -- e.g. 'starter', 'professional', 'enterprise'
    status                TEXT DEFAULT 'active',
    seats_total           INT DEFAULT 5,
    seats_used            INT DEFAULT 0,
    api_calls_this_month  BIGINT DEFAULT 0,
    api_call_limit        BIGINT DEFAULT 10000,
    renewal_date          DATE,
    created_at            TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE users (
    id          SERIAL PRIMARY KEY,
    account_id  INT REFERENCES accounts(id),
    email       TEXT UNIQUE,
    full_name   TEXT,
    role        TEXT DEFAULT 'member'
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

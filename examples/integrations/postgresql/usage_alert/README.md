# Usage Alert

**Direction:** Outbound

Proactively call accounts that have consumed 90%+ of their monthly API quota. The agent shares the current usage, gauges concern, and captures upgrade interest. The call outcome is logged to an `account_events` table.

## What it does

1. Fetches usage stats pre-call via a query on `accounts`
2. Delivers a usage warning and gauges interest in upgrading
3. Logs the call outcome to `account_events` via an `INSERT`

## Expected Schema

```sql
-- Extends the accounts table from account_lookup
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS api_calls_this_month BIGINT DEFAULT 0;
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS api_call_limit BIGINT DEFAULT 10000;

CREATE TABLE account_events (
    id          SERIAL PRIMARY KEY,
    account_id  INT REFERENCES accounts(id),
    event_type  TEXT,
    details     TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
```

## Suggested Trigger Query

Run this to find accounts to call:

```sql
SELECT id, name FROM accounts
WHERE status = 'active'
  AND api_call_limit > 0
  AND (api_calls_this_month::float / api_call_limit) >= 0.90
ORDER BY (api_calls_this_month::float / api_call_limit) DESC;
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
python __main__.py +15551234567 --account-id 42 --name "Jane Smith"
```

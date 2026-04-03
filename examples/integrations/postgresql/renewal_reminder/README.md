# Renewal Reminder

**Direction:** Outbound

Proactively calls customers ahead of their subscription renewal date. The agent confirms renewal intent and surfaces any changes the customer wants to make — such as switching plans or cancelling — before handing off to the account team. The call outcome is written to `account_events`.

## Expected Schema

```sql
CREATE TABLE accounts (
    id           SERIAL PRIMARY KEY,
    name         TEXT,
    plan         TEXT,
    status       TEXT DEFAULT 'active',
    renewal_date DATE,
    seats_total  INT,
    seats_used   INT
);

CREATE TABLE account_events (
    id         SERIAL PRIMARY KEY,
    account_id INT REFERENCES accounts(id),
    event_type TEXT,
    details    TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
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
python __main__.py +15551234567 --account-id 7 --name "Alex Chen"
```

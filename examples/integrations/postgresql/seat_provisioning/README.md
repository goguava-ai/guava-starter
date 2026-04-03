# Seat Provisioning

**Direction:** Inbound

An account admin calls to add seats to their Nexus Cloud subscription. The agent looks up their current seat usage, collects the number of additional seats needed, and logs a provisioning request in `seat_requests` for the account management team to action.

## Expected Schema

```sql
CREATE TABLE accounts (
    id           SERIAL PRIMARY KEY,
    name         TEXT,
    plan         TEXT,
    status       TEXT DEFAULT 'active',
    seats_total  INT DEFAULT 5,
    seats_used   INT DEFAULT 0,
    renewal_date DATE
);

CREATE TABLE users (
    id         SERIAL PRIMARY KEY,
    account_id INT REFERENCES accounts(id),
    email      TEXT UNIQUE,
    full_name  TEXT,
    role       TEXT DEFAULT 'member'  -- e.g. 'admin', 'member'
);

CREATE TABLE seat_requests (
    id               SERIAL PRIMARY KEY,
    account_id       INT REFERENCES accounts(id),
    contact_name     TEXT,
    seats_requested  INT,
    notes            TEXT,
    status           TEXT DEFAULT 'pending',
    created_at       TIMESTAMPTZ DEFAULT NOW()
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

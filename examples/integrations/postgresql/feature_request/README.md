# Feature Request

**Direction:** Inbound

A customer calls to suggest a new feature or product improvement. The agent verifies their account by email, collects a categorized and detailed feature description, and inserts a record into `feature_requests` for the product team.

## Expected Schema

```sql
CREATE TABLE accounts (
    id   SERIAL PRIMARY KEY,
    name TEXT,
    plan TEXT
);

CREATE TABLE users (
    id         SERIAL PRIMARY KEY,
    account_id INT REFERENCES accounts(id),
    email      TEXT UNIQUE,
    full_name  TEXT,
    role       TEXT DEFAULT 'member'
);

CREATE TABLE feature_requests (
    id              SERIAL PRIMARY KEY,
    account_id      INT REFERENCES accounts(id),
    contact_name    TEXT,
    contact_email   TEXT,
    category        TEXT,
    title           TEXT NOT NULL,
    description     TEXT,
    business_impact TEXT,
    status          TEXT DEFAULT 'submitted',
    created_at      TIMESTAMPTZ DEFAULT NOW()
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

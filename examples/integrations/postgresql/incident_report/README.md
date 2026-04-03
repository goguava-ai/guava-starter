# Incident Report

**Direction:** Inbound

A customer calls to report a technical issue. The agent collects the affected service, a full description, and impact level, maps the impact to a priority, and inserts an incident row into PostgreSQL.

## Expected Schema

```sql
CREATE TABLE incidents (
    id               SERIAL PRIMARY KEY,
    title            TEXT NOT NULL,
    description      TEXT,
    priority         TEXT CHECK (priority IN ('critical','high','medium','low')),
    status           TEXT DEFAULT 'open',
    reporter_name    TEXT,
    reporter_email   TEXT,
    affected_service TEXT,
    created_at       TIMESTAMPTZ DEFAULT NOW()
);
```

## Priority Mapping

| Caller's impact answer | Stored priority |
|---|---|
| Blocking my entire team | `critical` |
| Blocking me personally | `high` |
| Degraded but still working | `medium` |
| Minor inconvenience | `low` |

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

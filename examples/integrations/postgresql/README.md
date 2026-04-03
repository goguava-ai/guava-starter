# PostgreSQL Integration

Voice agents that read from and write to a PostgreSQL database — handling account lookups, incident reporting, and proactive usage alerts for a SaaS product.

Uses [`psycopg2`](https://www.psycopg.org/docs/) for all database operations.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`account_lookup`](account_lookup/) | Inbound | Customer calls to check their account plan, seat usage, and status |
| [`incident_report`](incident_report/) | Inbound | Customer reports an IT incident; agent creates a record in the database |
| [`usage_alert`](usage_alert/) | Outbound | Proactively call accounts that have consumed 90%+ of their monthly quota |
| [`billing_inquiry`](billing_inquiry/) | Inbound | Customer calls about an invoice or billing question; agent reads recent invoices |
| [`renewal_reminder`](renewal_reminder/) | Outbound | Proactively call accounts ahead of their subscription renewal date |
| [`feature_request`](feature_request/) | Inbound | Customer calls to submit a feature request; agent logs it for the product team |
| [`seat_provisioning`](seat_provisioning/) | Inbound | Account admin calls to add seats; agent logs a provisioning request |

## Connection

All examples use a `get_connection()` helper that returns a new `psycopg2` connection. Connections and cursors are used as context managers so they are closed reliably. `RealDictCursor` is used so rows are returned as plain dicts.

## Common Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `PGHOST` | PostgreSQL server hostname |
| `PGPORT` | PostgreSQL port (default: `5432`) |
| `PGUSER` | PostgreSQL username |
| `PGPASSWORD` | PostgreSQL password |
| `PGDATABASE` | Database name |

## Installation

```bash
pip install psycopg2-binary
```

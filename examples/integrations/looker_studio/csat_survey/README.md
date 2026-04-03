# CSAT Survey

**Direction:** Outbound

Calls a customer after a support ticket is resolved to collect a satisfaction score (1–5), whether their issue was fully resolved, and optional open feedback. Results land in BigQuery and feed a support quality dashboard in Looker Studio.

## BigQuery Table

```bash
bq mk --table YOUR_PROJECT_ID:guava_calls.csat_survey \
  call_timestamp:TIMESTAMP,contact_name:STRING,ticket_id:STRING,\
satisfaction_score:INTEGER,was_issue_resolved:STRING,feedback:STRING
```

## Looker Studio ideas

- **Average CSAT score** scorecard and trend line over time
- **Resolution rate** — pie chart of fully/partially/unresolved tickets
- **Score distribution** — bar chart of 1–5 ratings
- **Low-score table** — filter rows where `satisfaction_score <= 2` for follow-up

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `BIGQUERY_TABLE` | Fully-qualified BigQuery table (`project.dataset.table`) |

## Usage

```bash
python __main__.py +15551234567 --name "Jane Smith" --ticket-id TKT-4821
```

# Lead Qualification

**Direction:** Inbound

A prospect calls in and the agent qualifies them — collecting their company, role, use case, team size, and buying timeline. Every lead is logged to BigQuery so the sales team can track pipeline sources and segment leads in Looker Studio.

## BigQuery Table

```bash
bq mk --table YOUR_PROJECT_ID:guava_calls.lead_qualification \
  call_timestamp:TIMESTAMP,contact_name:STRING,contact_email:STRING,\
company_name:STRING,role:STRING,use_case:STRING,team_size:STRING,\
timeline:STRING,heard_from:STRING
```

## Looker Studio ideas

- **Leads by timeline** — bar chart showing how many leads are immediate vs. researching
- **Lead source breakdown** — pie chart of `heard_from` to track which channels drive calls
- **Role distribution** — understand who is calling (execs vs. ICs)
- **Team size filter** — segment high-value leads by `team_size`

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `BIGQUERY_TABLE` | Fully-qualified BigQuery table (`project.dataset.table`) |

## Usage

```bash
python __main__.py
```

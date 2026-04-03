# Sales Call Outcome

**Direction:** Outbound

Makes an outbound sales call, conducts a brief intro conversation, and logs the outcome — interest level, next step, and budget status — to BigQuery. Voicemail attempts are also logged with `reached=false`. Feeds a sales activity and pipeline dashboard in Looker Studio.

## BigQuery Table

```bash
bq mk --table YOUR_PROJECT_ID:guava_calls.sales_call_outcome \
  call_timestamp:TIMESTAMP,contact_name:STRING,company_name:STRING,\
interest_level:STRING,next_step:STRING,budget_confirmed:STRING,\
reached:BOOLEAN,notes:STRING
```

## Looker Studio ideas

- **Connect rate** — percentage of calls where `reached=true`
- **Interest funnel** — bar chart of `interest_level` distribution
- **Next step breakdown** — how many calls resulted in a demo, email, callback, or nothing
- **Call volume over time** — time series of daily/weekly outreach activity

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `BIGQUERY_TABLE` | Fully-qualified BigQuery table (`project.dataset.table`) |

## Usage

```bash
python __main__.py +15551234567 --name "Jane Smith" --company "Globex Corp"
```

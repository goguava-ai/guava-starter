# Churn Survey

**Direction:** Outbound

Calls recently cancelled customers to understand why they left. Collects the primary cancellation reason, whether they switched to a competitor, and whether they'd consider returning. Results land in BigQuery for a churn analysis dashboard in Looker Studio.

## BigQuery Table

```bash
bq mk --table YOUR_PROJECT_ID:guava_calls.churn_survey \
  call_timestamp:TIMESTAMP,contact_name:STRING,account_name:STRING,\
primary_reason:STRING,competitor_chosen:STRING,would_return:STRING,feedback:STRING
```

## Looker Studio ideas

- **Churn reasons** — pie or bar chart of `primary_reason` values
- **Competitor landscape** — frequency table of `competitor_chosen`
- **Return likelihood** — scorecard or donut chart of `would_return`
- **Trend** — churn reason distribution over time

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `BIGQUERY_TABLE` | Fully-qualified BigQuery table (`project.dataset.table`) |

## Usage

```bash
python __main__.py +15551234567 --name "Jane Smith" --account "Globex Corp"
```

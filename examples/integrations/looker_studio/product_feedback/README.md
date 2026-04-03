# Product Feedback

**Direction:** Outbound

Calls customers after a purchase to collect structured product feedback — a rating, usage frequency, favourite feature, and improvement suggestions. Results land in BigQuery and feed a product health dashboard in Looker Studio.

## BigQuery Table

```bash
bq mk --table YOUR_PROJECT_ID:guava_calls.product_feedback \
  call_timestamp:TIMESTAMP,contact_name:STRING,product_name:STRING,\
product_rating:INTEGER,usage_frequency:STRING,top_feature:STRING,\
improvement_suggestion:STRING,would_recommend:STRING
```

## Looker Studio ideas

- **Average rating** — scorecard per product, filterable by time range
- **Usage frequency** — bar chart showing how actively customers use the product
- **Recommendation rate** — donut chart of `would_recommend` values
- **Top features** — word cloud or table of the most mentioned features

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `BIGQUERY_TABLE` | Fully-qualified BigQuery table (`project.dataset.table`) |

## Usage

```bash
python __main__.py +15551234567 --name "Jane Smith" --product "Acme Pro Subscription"
```

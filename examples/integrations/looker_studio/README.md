# Looker Studio Integration

These examples show how to pipe Guava call data into **BigQuery** and visualize it in **Looker Studio**. After each call, one row is written to BigQuery. Looker Studio connects directly to that table — no extra infrastructure needed.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`__main__.py`](__main__.py) | Outbound | NPS survey — collect a 0–10 score and optional reason after a customer interaction |
| [`csat_survey`](csat_survey/) | Outbound | CSAT survey — satisfaction score and resolution status after a support ticket closes |
| [`churn_survey`](churn_survey/) | Outbound | Exit survey — why a customer cancelled and whether they'd return |
| [`lead_qualification`](lead_qualification/) | Inbound | Qualify inbound leads — role, use case, team size, and buying timeline |
| [`sales_call_outcome`](sales_call_outcome/) | Outbound | Log sales call outcomes — interest level, next step, and budget status |
| [`event_registration`](event_registration/) | Inbound | Register callers for an event — tickets, session preference, and dietary requirements |
| [`product_feedback`](product_feedback/) | Outbound | Post-purchase product feedback — rating, usage frequency, and improvement suggestions |
| [`win_loss_survey`](win_loss_survey/) | Outbound | Win/loss analysis — why a deal was won or lost and which competitor was in the running |

The original NPS example is at the root of this folder. All other examples follow the same pattern in their own subdirectories.

---

## How it works

```
Guava call → Fields collected → on_complete() → BigQuery row inserted → Looker Studio dashboard
```

The entire integration is in `save_to_bigquery()` — about 10 lines.

## Setup

### 1. Authenticate with Google Cloud

```bash
gcloud auth application-default login
```

This gives the BigQuery client credentials automatically. No service account file needed.

### 2. Create the BigQuery table

Replace `YOUR_PROJECT_ID` with your Google Cloud project ID.

```bash
bq mk --dataset YOUR_PROJECT_ID:guava_calls

bq mk --table YOUR_PROJECT_ID:guava_calls.nps_survey \
  call_timestamp:TIMESTAMP,contact_name:STRING,nps_score:INTEGER,reason:STRING
```

### 3. Install dependencies

```bash
pip install guava google-cloud-bigquery
```

### 4. Set environment variables

```bash
export GUAVA_AGENT_NUMBER="+1..."
export BIGQUERY_TABLE="YOUR_PROJECT_ID.guava_calls.nps_survey"
```

### 5. Run

```bash
python -m examples.integrations.looker_studio "+15551234567" --name "Jane Smith"
```

## Connect Looker Studio

1. Go to [lookerstudio.google.com](https://lookerstudio.google.com) and create a new report.
2. Click **Add data** → select **BigQuery**.
3. Choose your project → `guava_calls` dataset → `nps_survey` table.
4. Build charts — some ideas:
   - **Scorecard**: average NPS score across all calls
   - **Bar chart**: distribution of scores (0–10)
   - **Time series**: average score by day or week
   - **Table**: individual responses with contact name, score, and reason

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `BIGQUERY_TABLE` | Fully-qualified BigQuery table (`project.dataset.table`) |

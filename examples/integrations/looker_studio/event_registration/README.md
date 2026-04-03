# Event Registration

**Direction:** Inbound

Callers register for an event over the phone. The agent collects their name, email, ticket count, session preference, and dietary requirements, then logs each registration to BigQuery. Feeds an event attendance dashboard in Looker Studio.

## BigQuery Table

```bash
bq mk --table YOUR_PROJECT_ID:guava_calls.event_registration \
  call_timestamp:TIMESTAMP,full_name:STRING,email:STRING,company:STRING,\
ticket_count:INTEGER,session_preference:STRING,dietary_requirements:STRING,event_name:STRING
```

## Looker Studio ideas

- **Total registrations** — scorecard showing count of rows (total tickets sold)
- **Session demand** — bar chart of `session_preference` to plan capacity
- **Dietary breakdown** — pie chart for catering planning
- **Registrations over time** — time series to track sign-up momentum

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `BIGQUERY_TABLE` | Fully-qualified BigQuery table (`project.dataset.table`) |
| `EVENT_NAME` | Display name for the event (default: `Acme Corp Annual Conference`) |
| `EVENT_DATE` | Date string included in the agent's greeting (optional) |

## Usage

```bash
export EVENT_NAME="Product Summit 2026"
export EVENT_DATE="April 15, 2026"
python __main__.py
```

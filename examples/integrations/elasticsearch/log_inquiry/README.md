# Log Inquiry

**Direction:** Inbound

An on-call engineer calls to check application log activity. The agent collects the service name, log level filter, and time window, then queries Elasticsearch with a range + term filter and aggregation, and reads back a log count summary and the most recent error.

## What it does

1. Collects service name, log level filter, and time window
2. Searches via `POST /{log-index}/_search` with `bool` must filters for time range, service, and level
3. Uses a `terms` aggregation on `level.keyword` for a level breakdown
4. Reads back total count, level breakdown, and most recent error message

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `ELASTICSEARCH_URL` | Elasticsearch cluster URL |
| `ELASTICSEARCH_API_KEY` | Elasticsearch API key |
| `ELASTICSEARCH_LOG_INDEX` | Log index pattern (default: `logs-*`) |

## Usage

```bash
python -m examples.integrations.elasticsearch.log_inquiry
```

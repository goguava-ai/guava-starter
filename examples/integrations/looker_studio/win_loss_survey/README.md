# Win/Loss Survey

**Direction:** Outbound

Calls contacts after a deal closes — whether won or lost — to understand the deciding factor. The same script handles both outcomes, adjusting its tone based on the `--outcome` flag. Results land in BigQuery and feed a competitive intelligence dashboard in Looker Studio.

## BigQuery Table

```bash
bq mk --table YOUR_PROJECT_ID:guava_calls.win_loss_survey \
  call_timestamp:TIMESTAMP,contact_name:STRING,company_name:STRING,\
deal_outcome:STRING,main_reason:STRING,runner_up:STRING,feedback:STRING
```

## Looker Studio ideas

- **Win rate** — scorecard showing percentage of `deal_outcome = 'won'`
- **Win vs. loss reasons** — side-by-side bar charts of `main_reason` filtered by outcome
- **Competitive landscape** — frequency table of `runner_up` to track which competitors appear most
- **Trend** — win/loss ratio over time

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `BIGQUERY_TABLE` | Fully-qualified BigQuery table (`project.dataset.table`) |

## Usage

```bash
# Won deal
python __main__.py +15551234567 --name "Jane Smith" --company "Globex Corp" --outcome won

# Lost deal
python __main__.py +15551234567 --name "Jane Smith" --company "Globex Corp" --outcome lost
```

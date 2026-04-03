# Qlik Sense Integration

Voice agents that integrate with the [Qlik Cloud REST API](https://qlik.dev/apis/rest/qlik-cloud/) to trigger app reloads, notify stakeholders when reports are ready, and alert teams about data quality issues — bringing Qlik's analytics workflows into voice-driven automation.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`app_reload_request`](app_reload_request/) | Inbound | Employee calls to trigger a Qlik app data reload on demand |
| [`report_ready_notification`](report_ready_notification/) | Outbound | Agent calls a stakeholder when a scheduled Qlik reload completes successfully |
| [`data_quality_alert`](data_quality_alert/) | Outbound | Agent calls a data steward when a Qlik app reload fails or anomalies are detected |

## Authentication

All examples authenticate using a Qlik Cloud API key:

```python
HEADERS = {
    "Authorization": f"Bearer {QLIK_API_KEY}",
    "Content-Type": "application/json",
}
```

Generate an API key in Qlik Cloud: **User profile menu** → **Profile settings** → **API keys** → **Generate new key**.

## Common Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `QLIK_TENANT_URL` | Your Qlik Cloud tenant URL (e.g. `https://your-tenant.us.qlikcloud.com`) |
| `QLIK_API_KEY` | API key generated from the Qlik Cloud profile settings |

## Qlik Cloud API Reference

- [Apps API](https://qlik.dev/apis/rest/qlik-cloud/#tag/Apps)
- [Reloads API](https://qlik.dev/apis/rest/qlik-cloud/#tag/Reloads)
- [Reports API](https://qlik.dev/apis/rest/qlik-cloud/#tag/Reports)

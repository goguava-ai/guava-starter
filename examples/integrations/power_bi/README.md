# Microsoft Power BI Integration

Voice agents that integrate with the [Power BI REST API](https://learn.microsoft.com/en-us/rest/api/power-bi/) to trigger dataset refreshes, deliver KPI briefings over the phone, and alert stakeholders when metrics breach thresholds — turning data into actionable voice interactions.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`dataset_refresh_trigger`](dataset_refresh_trigger/) | Outbound | Agent calls a data owner to confirm, then triggers a Power BI dataset refresh |
| [`kpi_daily_briefing`](kpi_daily_briefing/) | Outbound | Morning call delivers a spoken summary of key metrics from a Power BI push dataset |
| [`alert_threshold_notification`](alert_threshold_notification/) | Outbound | Agent calls a stakeholder when a monitored KPI breaches a configured threshold |

## Authentication

All examples use OAuth2 Bearer tokens obtained via the Microsoft identity platform:

```python
import requests

def get_access_token(tenant_id, client_id, client_secret):
    resp = requests.post(
        f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "https://analysis.windows.net/powerbi/api/.default",
        },
    )
    resp.raise_for_status()
    return resp.json()["access_token"]
```

Register an Azure AD application and grant it Power BI API permissions (**Tenant.Read.All**, **Dataset.ReadWrite.All**). Enable the service principal in the Power BI Admin portal under **Developer settings**.

## Common Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `POWERBI_TENANT_ID` | Azure AD tenant ID |
| `POWERBI_CLIENT_ID` | Azure AD application (client) ID |
| `POWERBI_CLIENT_SECRET` | Azure AD client secret |
| `POWERBI_WORKSPACE_ID` | Power BI workspace (group) ID |

## Power BI API Reference

- [Datasets - Refresh Dataset](https://learn.microsoft.com/en-us/rest/api/power-bi/datasets/refresh-dataset)
- [Datasets - Get Refresh History](https://learn.microsoft.com/en-us/rest/api/power-bi/datasets/get-refresh-history)
- [Reports](https://learn.microsoft.com/en-us/rest/api/power-bi/reports)
- [Push Datasets](https://learn.microsoft.com/en-us/rest/api/power-bi/push-datasets)

# Tableau Integration

Voice agents that integrate with the [Tableau REST API](https://help.tableau.com/current/api/rest_api/en-us/REST/rest_api.htm) to check view freshness, handle access requests, deliver data briefings, and notify users of workbook refresh outcomes — all without opening a browser or logging into Tableau directly.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`view_status_check`](view_status_check/) | Inbound | Caller asks whether a specific Tableau view is fresh; agent looks it up and reports its last-updated time and current status |
| [`report_access_request`](report_access_request/) | Inbound | Caller requests access to a Tableau workbook; agent collects their details and tags the workbook for admin review |
| [`insight_briefing`](insight_briefing/) | Outbound | Proactively calls a stakeholder to deliver a verbal KPI briefing from a Tableau view and asks if they want a deeper review |
| [`workbook_refresh_notify`](workbook_refresh_notify/) | Outbound | Proactively calls a user to notify them that a workbook refresh has completed or failed and captures any follow-up needed |

## Authentication

All examples authenticate using Tableau **Personal Access Tokens (PATs)** via the Tableau REST API sign-in endpoint.

At module load time, each example calls `_signin()` which posts to:

```
POST https://<server>/api/3.21/auth/signin
```

with the request body:

```json
{
  "credentials": {
    "personalAccessTokenName": "...",
    "personalAccessTokenSecret": "...",
    "site": {"contentUrl": "..."}
  }
}
```

The response provides a session token and site ID used for all subsequent requests:

```
X-Tableau-Auth: <token>
```

Create a Personal Access Token in Tableau: **My Account Settings** → **Personal Access Tokens** → **Create new token**.

## Common Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `TABLEAU_SERVER_URL` | Tableau server base URL (e.g. `https://prod-ca-a.online.tableau.com`) |
| `TABLEAU_SITE_NAME` | Tableau site content URL (`contentUrl`); use an empty string for the default site |
| `TABLEAU_PAT_NAME` | Personal Access Token name |
| `TABLEAU_PAT_SECRET` | Personal Access Token secret |

## Tableau API Reference

- [REST API Overview](https://help.tableau.com/current/api/rest_api/en-us/REST/rest_api.htm)
- [Authentication](https://help.tableau.com/current/api/rest_api/en-us/REST/rest_api_concepts_auth.htm)
- [Workbooks and Views](https://help.tableau.com/current/api/rest_api/en-us/REST/rest_api_ref_workbooks_and_views.htm)
- [Permissions](https://help.tableau.com/current/api/rest_api/en-us/REST/rest_api_ref_permissions.htm)
- [Tags](https://help.tableau.com/current/api/rest_api/en-us/REST/rest_api_ref_workbooks_and_views.htm#add_tags_to_workbook)
- [API Version History](https://help.tableau.com/current/api/rest_api/en-us/REST/rest_api_concepts_versions.htm)

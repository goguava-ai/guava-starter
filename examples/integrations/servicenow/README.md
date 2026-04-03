# ServiceNow Customer Service Management Integration

Voice agents that integrate with the [ServiceNow REST API](https://developer.servicenow.com/dev.do#!/reference/api/tokyo/rest/c_TableAPI) to create cases, look up incident status, file IT incidents, and notify customers about planned maintenance — directly from a voice call.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`case_creation`](case_creation/) | Inbound | Customer calls with a support issue; agent creates a CSM case in ServiceNow |
| [`case_status_check`](case_status_check/) | Inbound | Customer calls to check the status of an existing case by case number |
| [`incident_report`](incident_report/) | Inbound | Employee reports an IT incident; ITIL impact/urgency matrix determines priority |
| [`change_notification`](change_notification/) | Outbound | Notify stakeholders about an upcoming planned change window; log acknowledgment as a work note |

## Authentication

All examples use HTTP Basic Authentication with ServiceNow username and password:

```python
AUTH = (SN_USERNAME, SN_PASSWORD)
requests.get(url, auth=AUTH, ...)
```

For production, use OAuth 2.0 or a dedicated integration service account with least-privilege roles.

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `SERVICENOW_INSTANCE` | Your ServiceNow instance name (e.g. `mycompany` → `mycompany.service-now.com`) |
| `SERVICENOW_USERNAME` | ServiceNow username |
| `SERVICENOW_PASSWORD` | ServiceNow password |

## ServiceNow Tables Used

| Table | API Path | Used In |
|---|---|---|
| Customer Service Case | `/api/now/table/sn_customerservice_case` | case_creation, case_status_check |
| Incident | `/api/now/table/incident` | incident_report |
| Change Request | `/api/now/table/change_request` | change_notification |

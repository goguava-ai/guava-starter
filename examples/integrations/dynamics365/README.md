# Microsoft Dynamics 365 Customer Service Integration

Voice agents that integrate with the [Dynamics 365 Web API](https://learn.microsoft.com/en-us/power-apps/developer/data-platform/webapi/overview) to handle inbound support calls, proactively reach customers, and keep case and contact records up to date — all without manual agent intervention.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`case_creation`](case_creation/) | Inbound | Customer calls to report an issue; agent looks up or creates their contact record and opens a Dynamics 365 support case |
| [`case_status_check`](case_status_check/) | Inbound | Customer calls to check their case status by case number or email address |
| [`contact_update`](contact_update/) | Inbound | Customer calls to update their phone number, email, or job title in Dynamics 365 |
| [`nps_survey`](nps_survey/) | Outbound | NPS survey call after a case is resolved; score and feedback written back to the case |
| [`churn_prevention`](churn_prevention/) | Outbound | Proactive retention call for at-risk customers; outcome written back to the contact record |

## Authentication

All examples authenticate to the Dynamics 365 Web API using an **OAuth 2.0 Bearer token** issued by **Azure Active Directory (Microsoft Entra ID)**.

Access tokens are short-lived (typically 60 minutes). For production workloads, use the **client credentials flow** with a service principal so tokens can be refreshed automatically:

1. Register an application in the [Azure portal](https://portal.azure.com) under **Azure Active Directory** → **App registrations**.
2. Grant the app the **Dynamics CRM — user_impersonation** API permission, or use application-level permissions and create a corresponding application user inside Dynamics 365.
3. Generate a client secret (or use a certificate) for the registered app.
4. Exchange the client credentials for a token:

```bash
curl -X POST \
  "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token" \
  -d "grant_type=client_credentials" \
  -d "client_id={client_id}" \
  -d "client_secret={client_secret}" \
  -d "scope=https://{yourorg}.crm.dynamics.com/.default"
```

The `access_token` field in the response is the Bearer token to supply as `DYNAMICS_ACCESS_TOKEN`.

For interactive / delegated scenarios, use the authorization code flow and store the refresh token so it can be exchanged for a new access token before each call batch.

## Common Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `DYNAMICS_ACCESS_TOKEN` | OAuth 2.0 Bearer token for the Dynamics 365 Web API |
| `DYNAMICS_ORG_URL` | Your Dynamics 365 organization URL (e.g. `https://yourorg.crm.dynamics.com`) |

## Dynamics 365 Web API Reference

- [Web API overview](https://learn.microsoft.com/en-us/power-apps/developer/data-platform/webapi/overview)
- [incidents (cases)](https://learn.microsoft.com/en-us/dynamics365/customer-service/developer/reference/entities/incident)
- [contacts](https://learn.microsoft.com/en-us/power-apps/developer/data-platform/webapi/reference/contact)
- [annotations (notes)](https://learn.microsoft.com/en-us/power-apps/developer/data-platform/webapi/reference/annotation)
- [phonecalls](https://learn.microsoft.com/en-us/power-apps/developer/data-platform/webapi/reference/phonecall)
- [Query data using the Web API](https://learn.microsoft.com/en-us/power-apps/developer/data-platform/webapi/query-data-web-api)
- [Authenticate to Dynamics 365 using OAuth](https://learn.microsoft.com/en-us/power-apps/developer/data-platform/authenticate-oauth)

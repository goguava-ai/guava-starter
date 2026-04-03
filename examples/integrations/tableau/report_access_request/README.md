# Report Access Request

**Direction:** Inbound

A caller wants to request access to a specific Tableau workbook or report. The agent collects their name, email, the workbook name, and an optional reason, then tags the workbook in Tableau with `access-requested` so an administrator knows to follow up.

## How It Works

1. Greets the caller and collects their name, email, workbook name, and optional access reason
2. Signs in to the Tableau REST API using a Personal Access Token to obtain a session token and site ID
3. Searches for the workbook by name via `GET /api/3.21/sites/<site_id>/workbooks?filter=name:eq:<name>`
4. Tags the workbook with `access-requested` via `PUT /api/3.21/sites/<site_id>/workbooks/<workbook_id>/tags`
5. Confirms to the caller that their request has been submitted and an admin will follow up by email

## Tableau API Calls

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/3.21/auth/signin` | Authenticate and obtain session token + site ID |
| `GET` | `/api/3.21/sites/<site_id>/workbooks?filter=name:eq:<name>` | Search for a workbook by name |
| `PUT` | `/api/3.21/sites/<site_id>/workbooks/<workbook_id>/tags` | Tag the workbook as access-requested |

## Setup

```bash
pip install guava requests
```

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `TABLEAU_SERVER_URL` | Tableau server base URL (e.g. `https://prod-ca-a.online.tableau.com`) |
| `TABLEAU_SITE_NAME` | Tableau site content URL (the `contentUrl` value for your site) |
| `TABLEAU_PAT_NAME` | Personal Access Token name |
| `TABLEAU_PAT_SECRET` | Personal Access Token secret |

## Usage

```bash
python -m examples.integrations.tableau.report_access_request
```

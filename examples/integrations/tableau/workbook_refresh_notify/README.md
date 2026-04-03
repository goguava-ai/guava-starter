# Workbook Refresh Notify

**Direction:** Outbound

Proactively calls a user to notify them that a Tableau workbook refresh has completed or failed. Shares the workbook name, last-updated timestamp, and size, then captures whether the user is satisfied or needs the analytics team to follow up.

## How It Works

1. Fetches workbook metadata pre-call via `GET /api/3.21/sites/<site_id>/workbooks/<workbook_id>` — captures name, `updatedAt`, and size
2. Reaches the user by name; leaves a voicemail if unavailable
3. Delivers the refresh status notification (completed or failed) with workbook details
4. Collects the user's satisfaction level (`satisfied`, `needs-review`, or `will-check-myself`) and any reported issues
5. Confirms next steps based on their response and ends the call

## Tableau API Calls

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/3.21/auth/signin` | Authenticate and obtain session token + site ID |
| `GET` | `/api/3.21/sites/<site_id>/workbooks/<workbook_id>` | Fetch workbook metadata (name, updatedAt, size) |

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
python -m examples.integrations.tableau.workbook_refresh_notify "+15551234567" --workbook-id wb123abc --name "James Rivera" --status completed
```

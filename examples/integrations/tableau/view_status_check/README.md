# View Status Check

**Direction:** Inbound

A caller asks whether a specific Tableau view is fresh and available. The agent looks up the view by name, reads its `updatedAt` timestamp, and reports whether it was updated within the last 24 hours.

## How It Works

1. Greets the caller and collects the view name (and optionally an alternate site URL)
2. Signs in to the Tableau REST API using a Personal Access Token to obtain a session token and site ID
3. Searches for the view via `GET /api/3.21/sites/<site_id>/views?filter=name:eq:<name>`
4. Reads the `updatedAt` field and computes how many hours ago it was last refreshed
5. Reports the view name, last-updated timestamp, owner, and whether it is current (within 24 hours)

## Tableau API Calls

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/3.21/auth/signin` | Authenticate and obtain session token + site ID |
| `GET` | `/api/3.21/sites/<site_id>/views?filter=name:eq:<name>` | Search for a view by name |

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
python -m examples.integrations.tableau.view_status_check
```

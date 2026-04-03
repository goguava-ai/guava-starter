# Insight Briefing

**Direction:** Outbound

Proactively calls a stakeholder to deliver a verbal summary of KPI metadata from a specific Tableau view. Shares the view name, owner, and last-updated timestamp, then asks whether the stakeholder wants to schedule a deeper review session with the analytics team.

## How It Works

1. Fetches view metadata pre-call via `GET /api/3.21/sites/<site_id>/views/<view_id>` — captures name, owner, and `updatedAt`
2. Reaches the stakeholder by name; leaves a voicemail if unavailable
3. Delivers a natural-language briefing with the view's metadata details
4. Collects whether the stakeholder wants to schedule a deeper review, and their preferred time if so
5. Confirms next steps and ends the call

## Tableau API Calls

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/3.21/auth/signin` | Authenticate and obtain session token + site ID |
| `GET` | `/api/3.21/sites/<site_id>/views/<view_id>` | Fetch view metadata (name, owner, updatedAt) |

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
python -m examples.integrations.tableau.insight_briefing "+15551234567" --view-id abc123def456 --name "Sarah Chen"
```

# Incident Report

**Direction:** Inbound

An employee calls the IT help desk to report an ITIL incident. The agent collects impact and urgency separately (following the ITIL matrix) and creates a properly prioritized Incident record in ServiceNow.

## What it does

1. Collects caller name, email, incident category, description, impact (who is affected), and urgency (how badly)
2. Computes priority using the ITIL impact × urgency matrix
3. Creates an Incident via `POST /api/now/table/incident`
4. Reads back the incident number and expected response SLA

## ITIL Priority Matrix (simplified)

| Impact | Urgency | Priority |
|---|---|---|
| Entire org | Cannot work | 1 – Critical |
| Entire org | Significant effort | 2 – High |
| Department | Cannot work | 2 – High |
| Department | Significant effort | 3 – Medium |
| Just me | Cannot work | 3 – Medium |
| Just me | Minor / significant | 4 – Low |

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `SERVICENOW_INSTANCE` | ServiceNow instance name |
| `SERVICENOW_USERNAME` | ServiceNow username |
| `SERVICENOW_PASSWORD` | ServiceNow password |

## Usage

```bash
python __main__.py
```

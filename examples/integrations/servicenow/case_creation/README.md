# Case Creation

**Direction:** Inbound

A customer calls with a support issue. The agent collects their contact details, categorizes the issue, and determines urgency — then creates a Customer Service Management case in ServiceNow.

## What it does

1. Collects caller name, email, company, issue category, description, and priority
2. Maps caller-described urgency to ServiceNow priority codes (1–4)
3. Creates a CSM case via `POST /api/now/table/sn_customerservice_case`
4. Reads back the case number to the caller

## Priority Mapping

| Caller Description | ServiceNow Priority |
|---|---|
| Critical — business is stopped | 1 (Critical) |
| High — major impact | 2 (High) |
| Medium — partial impact | 3 (Medium) |
| Low — minor inconvenience | 4 (Low) |

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

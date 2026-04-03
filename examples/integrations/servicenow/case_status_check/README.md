# Case Status Check

**Direction:** Inbound

A customer calls to check the status of an existing ServiceNow Customer Service case. The agent collects the case number, looks it up, and delivers a clear status update.

## What it does

1. Collects the caller's name and case number
2. Looks up the case via `GET /api/now/table/sn_customerservice_case?number={case_number}`
3. Reads back the state, priority, last-updated date, and assigned team

## State Labels

| ServiceNow State | Label |
|---|---|
| 1 | New |
| 2 | In Progress |
| 3 | On Hold |
| 4 | Resolved |
| 5 | Closed |
| 6 | Cancelled |

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

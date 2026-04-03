# Change Notification

**Direction:** Outbound

Call stakeholders to notify them about an upcoming planned maintenance window. The agent delivers the change details, captures acknowledgment, and logs the outcome as a work note on the ServiceNow Change Request.

## What it does

1. Fetches Change Request details pre-call via `GET /api/now/table/change_request?number={change_number}`
2. Calls the contact and delivers the maintenance window notification
3. Captures acknowledgment and whether they need to discuss an alternative window
4. Logs the outcome as a work note via `PATCH /api/now/table/change_request/{sys_id}`

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `SERVICENOW_INSTANCE` | ServiceNow instance name |
| `SERVICENOW_USERNAME` | ServiceNow username |
| `SERVICENOW_PASSWORD` | ServiceNow password |

## Usage

```bash
python __main__.py +15551234567 \
  --name "Jane Smith" \
  --change-number "CHG0012345" \
  --summary "Database maintenance and index rebuild on prod-db-01" \
  --window "Saturday April 5, 10 PM – 2 AM ET"
```

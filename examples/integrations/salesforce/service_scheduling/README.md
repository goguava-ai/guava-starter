# Service Scheduling

**Direction:** Inbound

A customer calls to schedule an on-site service appointment. The agent verifies their identity, captures the service type and preferred time slot, then creates a Salesforce Event and a linked Case for the technician to action.

## What it does

1. Looks up the caller's Contact by email via SOQL `GET /query`
2. Collects service type, issue description, preferred time slot, and site address
3. Creates a Salesforce Event via `POST /sobjects/Event`
4. Creates a linked Case via `POST /sobjects/Case` so the service team has a trackable work item

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `SALESFORCE_INSTANCE_URL` | Your Salesforce org URL |
| `SALESFORCE_ACCESS_TOKEN` | OAuth2 Bearer token |

## Usage

```bash
python __main__.py
```

> **Note:** Time slot offsets in this example are fixed relative offsets from the current date. In production, replace `SLOT_OFFSETS_DAYS` with a real availability lookup (e.g., Salesforce Scheduler or an external calendar API).

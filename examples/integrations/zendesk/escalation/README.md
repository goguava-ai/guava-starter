# Escalation — Zendesk Integration

An inbound voice agent that triages urgent support calls and creates an escalated ticket assigned directly to a senior support group. The ticket is created with `urgent` priority, typed as an `incident`, tagged for easy filtering, and routed to your Tier-2 team — all without the caller waiting on hold.

## How It Works

**1. Triage the issue**

The agent collects the caller's contact details, issue description, business impact, number of users affected, and a callback number. Gathering business impact early ensures the ticket captures enough context for the escalation team to act immediately.

**2. Detect critical situations**

After collection, the description and impact text are scanned for keywords like `outage`, `data loss`, `production`, and `security`. If detected, the closing instructions emphasize urgency and tell the caller the team is being paged.

**3. Create the escalated ticket**

`POST /api/v2/tickets` creates a ticket with:
- Priority: `urgent`
- Type: `incident`
- Subject prefixed with `[ESCALATED]`
- `group_id` set to your Tier-2 escalation group
- Tags: `escalated`, `voice`, `guava`

Assigning the `group_id` directly bypasses the default routing rules, so the ticket lands in the escalation queue immediately regardless of trigger configuration.

**4. Confirm to the caller**

The caller is given their ticket number and told a senior engineer will call them back at the number they provided. For flagged critical issues, they're told the team is being paged.

## Zendesk API Calls

| Timing | Endpoint | Purpose |
|---|---|---|
| Post-collection | `POST /api/v2/tickets` | Create an urgent incident ticket assigned to the escalation group |

## Finding Your Escalation Group ID

In Zendesk: **Admin Center** → **People** → **Groups** → click the group → the ID appears in the URL:
`https://yourcompany.zendesk.com/admin/people/teams/groups/**123456789**`

## Setup

### 1. Get a Zendesk API token

In Zendesk: **Admin Center** → **Apps and Integrations** → **APIs** → **Zendesk API** → **Add API token**.

### 2. Install dependencies

```bash
pip install guava requests
```

### 3. Set environment variables

```bash
export GUAVA_AGENT_NUMBER="+1..."
export ZENDESK_SUBDOMAIN="yourcompany"
export ZENDESK_EMAIL="agent@yourcompany.com"
export ZENDESK_API_TOKEN="<your_api_token>"
export ZENDESK_ESCALATION_GROUP_ID="123456789"
```

### 4. Run

```bash
python -m examples.integrations.zendesk.escalation
```

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `ZENDESK_SUBDOMAIN` | Your Zendesk subdomain |
| `ZENDESK_EMAIL` | Email of the Zendesk agent account used to authenticate |
| `ZENDESK_API_TOKEN` | Zendesk API token |
| `ZENDESK_ESCALATION_GROUP_ID` | Group ID for your Tier-2 / escalations team |

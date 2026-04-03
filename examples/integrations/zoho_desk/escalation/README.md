# Escalation — Zoho Desk Integration

An inbound voice agent that triages urgent and critical support calls. The agent collects issue details, business impact, and urgency reason, then either creates a new Urgent/Escalated ticket or upgrades an existing one — and attaches a private internal note with full escalation context.

## How It Works

**1. Triage the issue**

The agent collects the caller's name, email, an existing ticket ID (if they have one), a summary of the issue, the business impact, and the urgency reason.

**2. Existing ticket path**

If the caller provides a ticket ID, `GET /tickets/{id}` verifies it exists. If found, `PATCH /tickets/{id}` sets `priority: "Urgent"` and `status: "Escalated"`. A private internal note is posted via `POST /tickets/{id}/comments` with `isPublic: false`, capturing the urgency reason and business impact for the senior support team.

**3. New ticket path**

If no ticket ID is provided (or the existing ticket cannot be found), a new ticket is created via `POST /tickets` with `priority: "Urgent"`, `status: "Escalated"`, and tags `guava`, `voice`, and `escalated`. An internal note is then added with the full escalation context.

**4. Confirm to the caller**

The caller is given their ticket number (new or existing) and assured that the senior support team will review it immediately.

## Zoho Desk API Calls

| Timing | Endpoint | Purpose |
|---|---|---|
| Post-collection (existing ticket) | `GET /tickets/{id}` | Verify the existing ticket |
| Post-collection (existing ticket) | `PATCH /tickets/{id}` | Set priority to Urgent and status to Escalated |
| Post-collection | `POST /tickets/{id}/comments` | Add a private internal note with escalation context |
| Post-collection (new ticket) | `POST /tickets` | Create a new Urgent/Escalated ticket |

## Setup

### 1. Obtain a Zoho Desk OAuth access token

In Zoho Desk: **Setup** → **Developer Space** → **OAuth** to register a client and generate tokens. See the [Authentication](#authentication) section in the top-level README for details. Note that access tokens expire and must be refreshed periodically.

### 2. Install dependencies

```bash
pip install guava requests
```

### 3. Set environment variables

```bash
export GUAVA_AGENT_NUMBER="+1..."
export ZOHO_DESK_ACCESS_TOKEN="<your_access_token>"
export ZOHO_DESK_ORG_ID="<your_org_id>"
```

### 4. Run

```bash
python -m examples.integrations.zoho_desk.escalation
```

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `ZOHO_DESK_ACCESS_TOKEN` | Zoho OAuth 2.0 access token |
| `ZOHO_DESK_ORG_ID` | Your Zoho Desk organization ID |

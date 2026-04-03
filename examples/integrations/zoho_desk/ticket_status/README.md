# Ticket Status — Zoho Desk Integration

An inbound voice agent that looks up a caller's Zoho Desk support ticket status in real time. The caller can identify themselves by ticket number or email address, and the agent reads back the current status, priority, subject, and dates.

## How It Works

**1. Choose a lookup method**

The agent asks whether the caller wants to look up their ticket by ticket number or by the email address on their account.

**2. Look up by ticket number (Path A)**

If the caller provides a ticket number, `GET /tickets/{id}` fetches it directly and the agent reads back the full status.

**3. Look up by email (Path B)**

If the caller provides an email address, `GET /tickets?email={email}&limit=3` returns the most recent tickets associated with that email. The agent reads back the most recent one and notes if there are additional tickets on file.

**4. Read status and next steps**

The agent reports the ticket subject, current status (Open, On Hold, Escalated, or Closed), priority, creation date, and last update date. Closing instructions vary by status.

## Zoho Desk API Calls

| Timing | Endpoint | Purpose |
|---|---|---|
| Mid-call | `GET /tickets/{id}` | Direct ticket lookup by ticket number |
| Mid-call | `GET /tickets?email={email}&limit=3` | Search for tickets by email address |

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
python -m examples.integrations.zoho_desk.ticket_status
```

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `ZOHO_DESK_ACCESS_TOKEN` | Zoho OAuth 2.0 access token |
| `ZOHO_DESK_ORG_ID` | Your Zoho Desk organization ID |

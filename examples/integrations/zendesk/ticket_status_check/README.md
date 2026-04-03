# Ticket Status Check — Zendesk Integration

An inbound voice agent that looks up a caller's support ticket status in real time. The caller can provide a ticket ID directly or identify by email, and the agent reads back the current status and next steps.

## How It Works

**1. Collect identifier**

The agent asks for the caller's email and, optionally, their ticket number.

**2. Look up by ticket ID (Path A)**

If the caller provides a ticket number, `GET /api/v2/tickets/{id}` fetches it directly. This is the fastest path and works even if the caller's email has changed.

**3. Look up by email (Path B)**

If no ticket ID is given, or the ID lookup returns 404, `GET /api/v2/users/search?query={email}` finds the Zendesk user. Then `GET /api/v2/users/{id}/tickets/requested` fetches their most recent open or pending tickets, sorted by last update.

**4. Read status and next steps**

The agent reads back the ticket subject, current status (new, open, pending, on hold, solved, or closed), and priority. The closing instructions vary by status — pending tickets prompt the caller to reply to the email from our team; open tickets get a general "we'll be in touch" message.

## Zendesk API Calls

| Timing | Endpoint | Purpose |
|---|---|---|
| Mid-call | `GET /api/v2/tickets/{id}` | Direct ticket lookup by ID |
| Mid-call (fallback) | `GET /api/v2/users/search?query={email}` | Find user by email |
| Mid-call (fallback) | `GET /api/v2/users/{id}/tickets/requested` | List the user's recent tickets |

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
```

### 4. Run

```bash
python -m examples.integrations.zendesk.ticket_status_check
```

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `ZENDESK_SUBDOMAIN` | Your Zendesk subdomain |
| `ZENDESK_EMAIL` | Email of the Zendesk agent account used to authenticate |
| `ZENDESK_API_TOKEN` | Zendesk API token |

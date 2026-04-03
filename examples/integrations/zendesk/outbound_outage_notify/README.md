# Outbound Outage Notification — Zendesk Integration

An outbound voice campaign that automatically calls every customer with an open incident ticket linked to a problem ticket. When a production issue affects multiple customers simultaneously, this agent fetches the full list of impacted tickets, calls each requester, delivers a status update, and logs the outcome back to each individual ticket — without manually dialing a single number.

## How It Works

**1. Fetch all affected incident tickets**

`GET /api/v2/tickets/{problem_id}/incidents` returns all tickets linked to the central problem ticket. Open and pending incidents are kept; solved and closed ones are skipped.

**2. Resolve phone numbers**

For each incident ticket, `GET /api/v2/users/{requester_id}` retrieves the requester's profile. Tickets whose requester has no phone number on file are skipped (the customer will still receive the email notification Zendesk sends automatically).

**3. Call each customer**

`create_outbound()` places a call to each requester. All calls are initiated in sequence, and each runs as its own independent `OutageNotifyController` session.

**4. Deliver the update**

The `--outage-message` argument is spoken verbatim. The agent confirms the customer heard it and asks whether they'd like a callback once service is restored.

**5. Log the outcome per ticket**

`PUT /api/v2/tickets/{id}` posts a public comment to each ticket recording the call time, whether the customer was reached, and whether they requested a callback. Public comments ensure the requester sees the update in their email thread.

## Zendesk API Calls

| Timing | Endpoint | Purpose |
|---|---|---|
| Pre-campaign | `GET /api/v2/tickets/{problem_id}/incidents` | Fetch all open incident tickets |
| Pre-call (per ticket) | `GET /api/v2/users/{requester_id}` | Get requester name and phone number |
| Post-call (per ticket) | `PUT /api/v2/tickets/{id}` | Log call outcome as a public comment |

## Linking Incident Tickets to a Problem

To use the problem/incident relationship:
1. Create or designate a **problem ticket** (set `type: problem`) for the outage.
2. For each affected customer's ticket, set `type: incident` and `problem_id` to the problem ticket ID.

Zendesk also supports mass-linking via the UI: open the problem ticket → **Linked Incidents** → **Link Tickets**.

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
export ZENDESK_PROBLEM_TICKET_ID="98765"
```

### 4. Run

```bash
python -m examples.integrations.zendesk.outbound_outage_notify \
  --outage-message "We have identified an issue affecting API response times for some accounts. Our engineering team is actively working on a fix and we expect service to be fully restored within the next two hours."
```

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `ZENDESK_SUBDOMAIN` | Your Zendesk subdomain |
| `ZENDESK_EMAIL` | Email of the Zendesk agent account used to authenticate |
| `ZENDESK_API_TOKEN` | Zendesk API token |
| `ZENDESK_PROBLEM_TICKET_ID` | The Zendesk problem ticket ID for the active outage |

## Arguments

| Argument | Description |
|---|---|
| `--outage-message` | The status update message to deliver on each call — spoken verbatim |

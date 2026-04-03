# Ticket Update — Zendesk Integration

An inbound voice agent that lets customers call in to add information to an existing open support ticket. The agent verifies the ticket, collects the update, and posts it as a public comment — keeping the ticket thread complete without the customer needing to find and reply to an email.

## How It Works

**1. Collect ticket number and caller name**

The agent asks for the ticket ID and the caller's name. The name is included in the posted comment so agents can see who called in.

**2. Verify the ticket**

`GET /api/v2/tickets/{id}` fetches the ticket and confirms it exists and is still open. If the ticket is solved or closed, the caller is advised to open a new one.

**3. Collect the update**

The agent asks what new information the caller wants to add — symptoms, steps tried, error messages — and whether the issue is still ongoing or has since been resolved.

**4. Post the comment**

`PUT /api/v2/tickets/{id}` adds a public comment with the caller's name and update text. Public comments are visible to the ticket requester in their email thread and in the Zendesk help portal.

## Zendesk API Calls

| Timing | Endpoint | Purpose |
|---|---|---|
| After ticket ID collected | `GET /api/v2/tickets/{id}` | Verify the ticket exists and is still open |
| Post-collection | `PUT /api/v2/tickets/{id}` | Add a public comment with the caller's update |

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
python -m examples.integrations.zendesk.ticket_update
```

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `ZENDESK_SUBDOMAIN` | Your Zendesk subdomain |
| `ZENDESK_EMAIL` | Email of the Zendesk agent account used to authenticate |
| `ZENDESK_API_TOKEN` | Zendesk API token |

# Ticket Update — Zoho Desk Integration

An inbound voice agent that lets customers call in to add information to an existing Zoho Desk support ticket. The agent verifies the ticket and the caller's email, collects the update, and posts it as a public comment — keeping the ticket thread complete without the customer needing to find and reply to an email.

## How It Works

**1. Collect ticket ID and email**

The agent asks for the ticket number and the email address associated with the ticket. The email is used to verify that the caller owns the ticket before any changes are made.

**2. Verify the ticket**

`GET /tickets/{id}` fetches the ticket and confirms it exists and is still open. If the ticket is closed, the caller is advised to open a new one. If the email does not match the contact on file, the agent declines to update for security.

**3. Collect the update**

The agent asks what new information the caller wants to add and what type of update it is: new information, a status update request, an escalation request, or other.

**4. Post a public comment**

`POST /tickets/{id}/comments` with `isPublic: true` adds the update as a public comment visible to the customer in their email thread and in the Zoho Desk customer portal.

## Zoho Desk API Calls

| Timing | Endpoint | Purpose |
|---|---|---|
| After ticket ID collected | `GET /tickets/{id}` | Verify the ticket exists and is open, and check contact email |
| Post-collection | `POST /tickets/{id}/comments` | Add a public comment with the caller's update |

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
python -m examples.integrations.zoho_desk.ticket_update
```

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `ZOHO_DESK_ACCESS_TOKEN` | Zoho OAuth 2.0 access token |
| `ZOHO_DESK_ORG_ID` | Your Zoho Desk organization ID |

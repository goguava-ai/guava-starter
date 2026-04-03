# Proactive Update — Zendesk Integration

An outbound voice agent that calls customers to deliver a specific update on their support ticket. The agent fetches ticket context before placing the call, delivers the update, answers whether the customer has questions, and logs the call outcome as a private note on the ticket.

## How It Works

**1. Pre-call: fetch ticket context**

`GET /api/v2/tickets/{id}` retrieves the ticket subject and current status. `GET /api/v2/tickets/{id}/comments` fetches public comments sorted newest-first, and the most recent agent comment is extracted for context. This lets the agent reference the actual issue by name during the call.

**2. Reach the customer**

`reach_person()` places the outbound call. If the call goes to voicemail, a brief message is left and the unanswered attempt is logged on the ticket.

**3. Deliver the update**

The `--update` argument is spoken verbatim by the agent. This is the specific update message — for example, "Our engineering team has identified the root cause and a fix is being deployed to production now."

**4. Confirm and handle questions**

The agent confirms the customer understood, then asks if they have any questions. If they do, the question is captured and noted on the ticket for an agent to follow up on.

**5. Log the call outcome**

`PUT /api/v2/tickets/{id}` adds a private internal note recording the call date, customer name, whether they were reached, and any questions they raised. This creates an auditable trail of proactive outreach.

## Zendesk API Calls

| Timing | Endpoint | Purpose |
|---|---|---|
| Pre-call | `GET /api/v2/tickets/{id}` | Fetch ticket subject and status |
| Pre-call | `GET /api/v2/tickets/{id}/comments` | Get most recent public agent comment |
| Post-call | `PUT /api/v2/tickets/{id}` | Add private note with call outcome |

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
python -m examples.integrations.zendesk.proactive_update +15551234567 \
  --ticket-id 12345 \
  --name "Jane Smith" \
  --update "Our engineering team has identified the root cause and a fix is being deployed now. Your service should be fully restored within the next 30 minutes."
```

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `ZENDESK_SUBDOMAIN` | Your Zendesk subdomain |
| `ZENDESK_EMAIL` | Email of the Zendesk agent account used to authenticate |
| `ZENDESK_API_TOKEN` | Zendesk API token |

## Arguments

| Argument | Description |
|---|---|
| `phone` | Customer phone number in E.164 format (e.g. `+15551234567`) |
| `--ticket-id` | The Zendesk ticket ID to update |
| `--name` | Customer's full name |
| `--update` | The update message to deliver — spoken verbatim by the agent |

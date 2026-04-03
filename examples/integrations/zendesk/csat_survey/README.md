# CSAT Survey — Zendesk Integration

An outbound voice agent that calls customers after a support ticket is resolved to collect a customer satisfaction (CSAT) rating. Survey results are written back to the ticket as a private internal note, keeping feedback co-located with the case.

## How It Works

**1. Pre-call: fetch the ticket**

Before placing the call, `GET /api/v2/tickets/{id}` retrieves the ticket subject. This lets the agent reference the specific issue by name ("your ticket about the login error") instead of a generic phrase.

**2. Reach the customer**

`reach_person()` places the outbound call and waits for a live person to answer. If the call goes to voicemail, `on_failure` leaves a brief non-intrusive message and hangs up.

**3. Collect feedback**

The agent asks three questions:
- **Satisfaction rating**: 1–5 scale (1 = very dissatisfied, 5 = very satisfied)
- **Resolution quality**: whether the issue was fully resolved, partially, or not at all
- **Open feedback**: any additional comments (optional)

**4. Write results back to Zendesk**

`PUT /api/v2/tickets/{id}` posts a private internal note with the full survey results. Private notes are visible only to agents in Zendesk — they do not trigger customer-facing email notifications.

**5. Close appropriately**

If the rating is 1 or 2, the agent acknowledges the poor experience and promises a personal follow-up from the team. Higher ratings get a warm thank-you.

## Zendesk API Calls

| Timing | Endpoint | Purpose |
|---|---|---|
| Pre-call | `GET /api/v2/tickets/{id}` | Fetch ticket subject to personalize the survey |
| Post-survey | `PUT /api/v2/tickets/{id}` | Add a private internal note with CSAT results |

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
python -m examples.integrations.zendesk.csat_survey +15551234567 \
  --ticket-id 12345 \
  --name "Jane Smith"
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
| `--ticket-id` | The resolved Zendesk ticket ID |
| `--name` | Customer's full name |

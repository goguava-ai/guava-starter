# CSAT Survey — Zoho Desk Integration

An outbound voice agent that calls customers after a Zoho Desk support ticket is resolved to collect a customer satisfaction (CSAT) rating. Survey results are written back to the ticket as a private internal note, and the ticket is closed automatically if the customer reports full resolution.

## How It Works

**1. Pre-call: fetch the ticket**

Before placing the call, `GET /tickets/{id}` retrieves the ticket subject and contact information. This lets the agent reference the specific issue by name rather than a generic phrase.

**2. Reach the customer**

`reach_person()` places the outbound call and waits for a live person to answer. If the call goes to voicemail, `on_failure` leaves a brief, non-intrusive message and hangs up.

**3. Collect feedback**

The agent asks three questions:
- **Satisfaction rating**: 1–5 scale (1 = very dissatisfied, 5 = very satisfied)
- **Resolution quality**: whether the issue was fully resolved, partially resolved, or not resolved
- **Open feedback**: any additional comments (optional)

**4. Write results back to Zoho Desk**

`POST /tickets/{id}/comments` with `isPublic: false` posts a private internal note with the full survey results. Internal notes are visible only to agents and do not trigger customer-facing email notifications.

**5. Close the ticket if fully resolved**

If the customer selects `fully-resolved`, `PATCH /tickets/{id}` updates the ticket status to `Closed`.

**6. Close appropriately**

If the rating is 1 or 2, the agent acknowledges the poor experience and promises a personal follow-up. Higher ratings receive a warm thank-you.

## Zoho Desk API Calls

| Timing | Endpoint | Purpose |
|---|---|---|
| Pre-call | `GET /tickets/{id}` | Fetch ticket subject to personalize the survey |
| Post-survey | `POST /tickets/{id}/comments` | Add a private internal note with CSAT results |
| Post-survey (if fully resolved) | `PATCH /tickets/{id}` | Set ticket status to Closed |

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
python -m examples.integrations.zoho_desk.csat_survey +15551234567 \
  --ticket-id 123456789 \
  --name "Jane Smith"
```

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `ZOHO_DESK_ACCESS_TOKEN` | Zoho OAuth 2.0 access token |
| `ZOHO_DESK_ORG_ID` | Your Zoho Desk organization ID |

## Arguments

| Argument | Description |
|---|---|
| `phone` | Customer phone number in E.164 format (e.g. `+15551234567`) |
| `--ticket-id` | The resolved Zoho Desk ticket ID |
| `--name` | Customer's full name |

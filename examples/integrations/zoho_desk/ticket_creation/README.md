# Ticket Creation — Zoho Desk Integration

An inbound voice agent that answers support calls, collects the caller's contact details, issue type, and description, and opens a Zoho Desk ticket on their behalf — all within the call.

## How It Works

**1. Greet and collect contact info**

The agent introduces itself and gathers the caller's name and email address. These are sent to Zoho Desk as the ticket contact so email notifications reach the right person.

**2. Categorize the issue**

The caller selects the type of issue they're experiencing: billing, technical issue, account access, feature request, or other. This is included in the ticket subject for easy triage.

**3. Capture the issue**

The agent asks for a brief summary and any additional detail (steps to reproduce, error messages, duration). Both are combined into the ticket description.

**4. Set priority**

The caller is asked how urgently the issue is affecting their work. Their answer is mapped to one of Zoho Desk's priority levels (`Low`, `Medium`, `High`, `Urgent`).

**5. Create the ticket**

`POST /tickets` creates the ticket with `channel: "Voice"` and the `guava` and `voice` tags applied for easy filtering. The ticket opens with `status: "Open"`.

**6. Confirm the ticket number**

The agent reads back the `ticketNumber` from the response so the caller has it for future reference before hanging up.

## Zoho Desk API Calls

| Timing | Endpoint | Purpose |
|---|---|---|
| Post-collection | `POST /tickets` | Create the support ticket with contact and issue details |

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
python -m examples.integrations.zoho_desk.ticket_creation
```

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `ZOHO_DESK_ACCESS_TOKEN` | Zoho OAuth 2.0 access token |
| `ZOHO_DESK_ORG_ID` | Your Zoho Desk organization ID |

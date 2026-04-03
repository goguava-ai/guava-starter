# Ticket Creation — Zendesk Integration

An inbound voice agent that answers support calls, collects the caller's contact details and issue description, and opens a Zendesk ticket on their behalf — all within the call.

## How It Works

**1. Greet and collect contact info**

The agent introduces itself and gathers the caller's name and email address. These become the ticket requester so Zendesk's email notifications go to the right place.

**2. Capture the issue**

The agent asks for a brief summary and any additional detail (steps to reproduce, error messages, duration). Both are combined into the ticket's first comment body.

**3. Set priority**

The caller is asked how urgently the issue is affecting their work. Their answer is mapped to one of Zendesk's four priority levels (`low`, `normal`, `high`, `urgent`).

**4. Create the ticket**

`POST /api/v2/tickets` creates the ticket with the `voice` and `guava` tags applied for easy filtering in Zendesk views. If the requester email is new to Zendesk, an end-user record is created automatically.

**5. Confirm the ticket number**

The agent reads back the ticket ID so the caller has it for future reference before hanging up.

## Zendesk API Calls

| Timing | Endpoint | Purpose |
|---|---|---|
| Post-collection | `POST /api/v2/tickets` | Create the support ticket with requester and issue details |

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
python -m examples.integrations.zendesk.ticket_creation
```

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `ZENDESK_SUBDOMAIN` | Your Zendesk subdomain (e.g. `yourcompany` for `yourcompany.zendesk.com`) |
| `ZENDESK_EMAIL` | Email of the Zendesk agent account used to authenticate |
| `ZENDESK_API_TOKEN` | Zendesk API token |

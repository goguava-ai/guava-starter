# User Registration — Zendesk Integration

An inbound voice agent that handles first-time callers by checking whether they already have a Zendesk account, creating one if they don't, and opening their first support ticket — all in a single call. Returning callers are identified by email and linked to their existing record.

## How It Works

**1. Collect contact and issue details**

The agent gathers name, email, optional phone number, company, and a summary of their issue.

**2. Check for an existing user**

`GET /api/v2/users/search?query={email}` searches for an existing end-user record. Only `end-user` role results are considered — agents and admins are excluded.

**3. Create the user if needed**

If no existing record is found, `POST /api/v2/users` creates a new end-user with:
- `verified: true` so they can immediately access the help portal without an email confirmation step
- `organization.name` set to their company name — Zendesk looks up or creates the organization automatically

**4. Open the support ticket**

`POST /api/v2/tickets` creates the ticket using `requester_id` (the Zendesk user ID) rather than the inline `requester` object. This ensures the ticket is linked to the full user record rather than creating a duplicate contact.

**5. Confirm to the caller**

New users are told to expect a welcome email. Both new and returning users receive their ticket number.

## Zendesk API Calls

| Timing | Endpoint | Purpose |
|---|---|---|
| Post-collection | `GET /api/v2/users/search?query={email}` | Check for an existing end-user by email |
| Post-collection (new users) | `POST /api/v2/users` | Create the new end-user record |
| Post-registration | `POST /api/v2/tickets` | Open the support ticket linked to the user |

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
python -m examples.integrations.zendesk.user_registration
```

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `ZENDESK_SUBDOMAIN` | Your Zendesk subdomain |
| `ZENDESK_EMAIL` | Email of the Zendesk agent account used to authenticate |
| `ZENDESK_API_TOKEN` | Zendesk API token |

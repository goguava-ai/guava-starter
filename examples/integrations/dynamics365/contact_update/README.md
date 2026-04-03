# Contact Update — Dynamics 365 Integration

An inbound voice agent that lets customers update their contact information stored in Dynamics 365 — phone number, email address, and job title — by calling in and verifying their existing email address.

## How It Works

**1. Greet and collect current email**

The agent asks for the email address currently on the caller's account. This is used to locate their contact record.

**2. Look up the contact**

`GET /contacts?$filter=emailaddress1 eq '{email}'` finds the contact. If no record is found, the agent tells the caller and suggests alternatives.

**3. Collect the new values**

The agent asks which field(s) the caller wants to update and collects the new values. The caller can update any combination of phone, email, and job title, or select "all" to update multiple fields in one call.

**4. Apply the changes**

`PATCH /contacts({contact_id})` is called once with all changed fields: `telephone1` for phone, `emailaddress1` for email, and `jobtitle` for job title.

**5. Confirm the updates**

The agent tells the caller exactly which fields were updated and that the changes are effective immediately.

## Dynamics 365 API Calls

| Timing | Endpoint | Purpose |
|---|---|---|
| Post-collection | `GET /contacts` | Look up contact by current email |
| Post-collection | `PATCH /contacts({id})` | Apply updated field values |

## Field Name Mapping

| Spoken field | Dynamics 365 field |
|---|---|
| Phone number | `telephone1` |
| Email address | `emailaddress1` |
| Job title | `jobtitle` |

## Setup

### 1. Obtain an access token

See the top-level [Authentication](#) section in the Dynamics 365 integration README.

### 2. Install dependencies

```bash
pip install guava requests
```

### 3. Set environment variables

```bash
export GUAVA_AGENT_NUMBER="+1..."
export DYNAMICS_ACCESS_TOKEN="<your_bearer_token>"
export DYNAMICS_ORG_URL="https://yourorg.crm.dynamics.com"
```

### 4. Run

```bash
python -m examples.integrations.dynamics365.contact_update
```

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `DYNAMICS_ACCESS_TOKEN` | OAuth 2.0 Bearer token for the Dynamics 365 Web API |
| `DYNAMICS_ORG_URL` | Your Dynamics 365 organization URL (e.g. `https://yourorg.crm.dynamics.com`) |

# Churn Prevention — Dynamics 365 Integration

An outbound voice agent that proactively contacts at-risk customers to understand their concerns, gauge their likelihood of renewal, and surface the right next step — then writes the outcome back to Dynamics 365 as an internal note and a logged phone call activity on the contact record.

## How It Works

**1. Pre-call: fetch contact details**

Before dialing, `GET /contacts({contact_id})?$select=fullname,emailaddress1,telephone1,accountid` retrieves the contact record to confirm details and provide context.

**2. Reach the customer**

The agent dials the provided number and attempts to reach the named contact. If unavailable, it leaves a brief professional voicemail inviting a callback.

**3. Collect retention data**

The agent collects:
- Overall satisfaction (very-satisfied → very-dissatisfied)
- Primary concern (optional — surfaced for dissatisfied or neutral customers)
- Likelihood to renew (very-likely → not-renewing)
- Requested next step (account manager / technical support / pricing review / no action)

**4. Write back to Dynamics 365**

`POST /annotations` attaches the retention call notes directly to the contact record (using `objectid_contact@odata.bind` and `objecttypecode: "contact"`). `POST /phonecalls` logs the call as an outbound phone activity against the same contact.

**5. Tailor the closing**

The agent's closing message is personalized based on the requested next step — setting concrete expectations for account manager outreach, technical support, or a pricing review.

## Dynamics 365 API Calls

| Timing | Endpoint | Purpose |
|---|---|---|
| Pre-call | `GET /contacts({id})` | Fetch contact details |
| Post-call | `POST /annotations` | Write retention notes to the contact record |
| Post-call | `POST /phonecalls` | Log the outbound retention call against the contact |

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
python -m examples.integrations.dynamics365.churn_prevention +15551234567 --contact-id <contact-guid> --name "Jane Smith"
```

## Arguments

| Argument | Description |
|---|---|
| `phone` | Customer phone number in E.164 format (e.g. `+15551234567`) |
| `--contact-id` | Dynamics 365 contact ID — the GUID from the `contactid` field |
| `--name` | Customer's full name |

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `DYNAMICS_ACCESS_TOKEN` | OAuth 2.0 Bearer token for the Dynamics 365 Web API |
| `DYNAMICS_ORG_URL` | Your Dynamics 365 organization URL (e.g. `https://yourorg.crm.dynamics.com`) |

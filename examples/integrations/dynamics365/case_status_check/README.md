# Case Status Check — Dynamics 365 Integration

An inbound voice agent that lets customers check the status of their Dynamics 365 support cases by case number or by the email address on their account.

## How It Works

**1. Greet and collect lookup preference**

The agent asks whether the caller wants to look up their case by case number (e.g. `CAS-12345-ABCDEF`) or by email address.

**2. Look up the case**

- **By case number**: `GET /incidents?$filter=ticketnumber eq '{number}'` retrieves the case directly.
- **By email**: `GET /contacts?$filter=emailaddress1 eq '{email}'` finds the contact, then `GET /incidents?$filter=_customerid_value eq '{contact_id}'&$orderby=createdon desc&$top=3` retrieves their most recent cases.

**3. Report the status**

The agent maps the numeric `statuscode` to a friendly label and reads back the case title, status, priority, and creation date. If the email lookup returned multiple cases the caller is informed they can call back to check the others.

## Status Code Mapping

| Code | Label |
|---|---|
| 1 | In Progress |
| 2 | On Hold |
| 3 | Waiting for Details |
| 4 | Researching |
| 5 | Resolved |
| 6 | Cancelled |

## Dynamics 365 API Calls

| Timing | Endpoint | Purpose |
|---|---|---|
| Post-collection | `GET /incidents` | Look up case by ticket number |
| Post-collection | `GET /contacts` | Find contact by email (email path) |
| Post-collection | `GET /incidents` | Fetch most recent cases for the contact (email path) |

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
python -m examples.integrations.dynamics365.case_status_check
```

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `DYNAMICS_ACCESS_TOKEN` | OAuth 2.0 Bearer token for the Dynamics 365 Web API |
| `DYNAMICS_ORG_URL` | Your Dynamics 365 organization URL (e.g. `https://yourorg.crm.dynamics.com`) |

# Case Creation — Dynamics 365 Integration

An inbound voice agent that answers support calls, collects the caller's contact details and issue description, looks up or creates their contact record, and opens a Dynamics 365 support case on their behalf — all within the call.

## How It Works

**1. Greet and collect contact info**

The agent introduces itself and gathers the caller's name and email address. These are used to look up or create a contact record in Dynamics 365.

**2. Capture the issue**

The agent asks for the issue type, a brief summary, and optional additional detail. Both are combined into the case description.

**3. Set priority**

The caller is asked how urgently the issue is affecting their work. Their answer is mapped to a Dynamics 365 priority code (1=High, 2=Normal, 3=Low).

**4. Look up or create the contact**

`GET /contacts?$filter=emailaddress1 eq '{email}'` checks whether a contact record already exists. If not, `POST /contacts` creates one.

**5. Create the case**

`POST /incidents` creates the support case linked to the contact, with the issue type prepended to the title and the priority code set accordingly.

**6. Add an internal note**

`POST /annotations` attaches a private note to the case with the caller's name, email, issue type, and details — providing full context for the support team.

**7. Confirm the case number**

The agent reads back the ticket number (e.g. `CAS-12345-ABCDEF`) so the caller has it for future reference.

## Dynamics 365 API Calls

| Timing | Endpoint | Purpose |
|---|---|---|
| Post-collection | `GET /contacts` | Look up contact by email |
| Post-collection | `POST /contacts` | Create contact if not found |
| Post-collection | `POST /incidents` | Create the support case |
| Post-collection | `POST /annotations` | Add internal note with caller details |

## Setup

### 1. Obtain an access token

See the top-level [Authentication](#) section in the Dynamics 365 integration README for how to obtain an OAuth 2.0 Bearer token via Azure AD / Microsoft Entra ID.

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
python -m examples.integrations.dynamics365.case_creation
```

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `DYNAMICS_ACCESS_TOKEN` | OAuth 2.0 Bearer token for the Dynamics 365 Web API |
| `DYNAMICS_ORG_URL` | Your Dynamics 365 organization URL (e.g. `https://yourorg.crm.dynamics.com`) |

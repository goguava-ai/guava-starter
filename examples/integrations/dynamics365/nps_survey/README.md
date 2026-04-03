# NPS Survey — Dynamics 365 Integration

An outbound voice agent that calls customers after a Dynamics 365 support case is resolved, collects their Net Promoter Score and qualitative feedback, and writes the results back to the case as an internal note and a logged phone call activity.

## How It Works

**1. Pre-call: fetch case details**

Before dialing, `GET /incidents({case_id})?$select=title,ticketnumber,statuscode` retrieves the case title and ticket number to personalize the conversation.

**2. Reach the customer**

The agent dials the provided number and attempts to reach the named contact. If unavailable, it leaves a brief voicemail.

**3. Collect NPS feedback**

The agent asks for:
- An NPS score from 0 to 10
- The primary reason for that score
- An optional improvement suggestion

**4. Write back to Dynamics 365**

`POST /annotations` attaches the survey results as an internal note on the resolved case. `POST /phonecalls` logs the call as an outbound phone activity against the same case.

**5. Tailor the closing**

Promoters (9-10) receive a warm thank-you. Passives (7-8) receive a standard thank-you. Detractors (0-6) are told that a member of the customer success team will personally follow up.

## NPS Categories

| Score | Category |
|---|---|
| 9–10 | Promoter |
| 7–8 | Passive |
| 0–6 | Detractor |

## Dynamics 365 API Calls

| Timing | Endpoint | Purpose |
|---|---|---|
| Pre-call | `GET /incidents({id})` | Fetch case title and ticket number |
| Post-survey | `POST /annotations` | Write NPS results as an internal note on the case |
| Post-survey | `POST /phonecalls` | Log the outbound survey call against the case |

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
python -m examples.integrations.dynamics365.nps_survey +15551234567 --case-id <incident-guid> --name "Jane Smith"
```

## Arguments

| Argument | Description |
|---|---|
| `phone` | Customer phone number in E.164 format (e.g. `+15551234567`) |
| `--case-id` | Dynamics 365 incident (case) ID — the GUID from the `incidentid` field |
| `--name` | Customer's full name |

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `DYNAMICS_ACCESS_TOKEN` | OAuth 2.0 Bearer token for the Dynamics 365 Web API |
| `DYNAMICS_ORG_URL` | Your Dynamics 365 organization URL (e.g. `https://yourorg.crm.dynamics.com`) |

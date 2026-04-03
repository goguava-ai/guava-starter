# Claim Status Inquiry — Waystar Integration

An inbound voice agent that looks up the status of a submitted claim through the Waystar RCM platform. Billing staff or patients provide the patient's member ID, date of birth, and service date, and the agent returns the current claim status, adjudicated amount, and patient responsibility.

## How It Works

**1. Collect lookup details**

The agent gathers patient last name, DOB, member ID, service date, and an optional payer claim number.

**2. Submit a claim status inquiry**

`get_claim_status()` posts to `POST /claimstatus/v1/inquiries`. If a claim number is provided, it is included to narrow the search.

**3. Parse the response**

`parse_status_response()` extracts status, payer claim number, adjudicated amount, patient responsibility, and denial reason from the first claim in the response.

**4. Report status to the caller**

All relevant details are read to the caller. Denied claims prompt a note that the billing team will review.

## Waystar API Calls

| Timing | Method | Endpoint | Purpose |
|---|---|---|---|
| Pre-call | `POST` | `/auth/oauth2/token` | Obtain OAuth access token |
| Mid-call | `POST` | `/claimstatus/v1/inquiries` | Submit claim status inquiry |

## Setup

```bash
export GUAVA_AGENT_NUMBER="+1..."
export WAYSTAR_CLIENT_ID="..."
export WAYSTAR_CLIENT_SECRET="..."
export WAYSTAR_PAYER_ID="00001"
export PROVIDER_NPI="1234567890"
```

## Run

```bash
python -m examples.integrations.waystar.claim_status_inquiry
```

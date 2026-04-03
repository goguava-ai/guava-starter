# Prior Auth Lookup — Waystar Integration

An inbound voice agent that checks prior authorization status for scheduled procedures through the Waystar platform. Clinical or administrative staff provide patient and procedure details and the agent returns the authorization decision, number, and validity window.

## How It Works

**1. Collect patient and procedure details**

The agent gathers patient name, DOB, member ID, procedure description, optional CPT code, and planned service date.

**2. Submit a prior auth inquiry**

`lookup_prior_auth()` posts to `POST /priorauth/v1/inquiries` with subscriber and service details.

**3. Parse the authorization response**

`parse_auth_result()` extracts the decision (approved/denied/pending), authorization number, effective and expiration dates, and approved units.

**4. Communicate the decision**

The agent adapts its response to the decision: confirming approved authorizations with reference numbers, acknowledging denials with appeal options, or flagging pending cases for follow-up.

## Waystar API Calls

| Timing | Method | Endpoint | Purpose |
|---|---|---|---|
| Pre-call | `POST` | `/auth/oauth2/token` | Obtain OAuth access token |
| Mid-call | `POST` | `/priorauth/v1/inquiries` | Submit prior auth inquiry |

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
python -m examples.integrations.waystar.prior_auth_lookup
```

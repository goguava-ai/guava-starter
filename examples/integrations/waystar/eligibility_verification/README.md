# Eligibility Verification — Waystar Integration

An inbound voice agent that performs real-time insurance eligibility checks using the Waystar platform. Patients or front-desk staff call in, provide insurance and identity details, and the agent returns coverage status, copay, deductible, and out-of-pocket information.

## How It Works

**1. Collect patient identity and insurance details**

The agent gathers first name, last name, date of birth, member ID, and insurance company name.

**2. Submit an eligibility inquiry**

`verify_eligibility()` posts to `POST /eligibility/v1/inquiries` with subscriber and provider information.

**3. Extract coverage details**

`extract_coverage_summary()` processes the `coverages` array, mapping coverage types to key benefit fields: active status, plan name, copay, deductible, and out-of-pocket maximum.

**4. Read coverage back to the caller**

Active coverage details are read aloud. If coverage cannot be confirmed, the caller is directed to their insurance company.

## Waystar API Calls

| Timing | Method | Endpoint | Purpose |
|---|---|---|---|
| Pre-call | `POST` | `/auth/oauth2/token` | Obtain OAuth access token |
| Mid-call | `POST` | `/eligibility/v1/inquiries` | Submit real-time eligibility inquiry |

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
python -m examples.integrations.waystar.eligibility_verification
```

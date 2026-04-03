# Prior Auth Status — Change Healthcare Integration

An inbound voice agent that checks the prior authorization status for a scheduled procedure. Clinical or administrative staff call in, provide patient and procedure details, and the agent submits a 278 inquiry to the payer through Change Healthcare.

## How It Works

**1. Collect patient and procedure details**

The agent gathers the patient's name, DOB, member ID, procedure description, optional CPT code, and planned service date.

**2. Submit a 278 prior auth inquiry**

`check_prior_auth()` posts to `POST /medicalnetwork/priorauthorization/v3`. The `serviceReview` block includes the procedure code and service date.

**3. Parse the 278 response**

`parse_auth_response()` maps the `actionCode` to a status:
- `A1` — Certified/Approved
- `A2` — Not Certified/Denied
- `A3` — Modified/Partial Approval
- `A4` — Additional Information Required
- `A6` — Modified/Services Certified

Authorization number, effective date, and expiration date are also extracted if present.

**4. Communicate the result**

The agent reads the authorization status, reference number, and validity window. If additional information is required, the caller is told a clinical team member will follow up.

## Change Healthcare API Calls

| Timing | Method | Endpoint | Purpose |
|---|---|---|---|
| Pre-call | `POST` | `/apip/auth/v2/token` | Obtain OAuth access token |
| Mid-call | `POST` | `/medicalnetwork/priorauthorization/v3` | Submit 278 authorization inquiry |

## Setup

```bash
export GUAVA_AGENT_NUMBER="+1..."
export CHANGE_HEALTHCARE_CLIENT_ID="..."
export CHANGE_HEALTHCARE_CLIENT_SECRET="..."
export CHANGE_HEALTHCARE_TRADING_PARTNER_ID="000050"
export PROVIDER_NPI="1234567890"
```

## Run

```bash
python -m examples.integrations.change_healthcare.prior_auth_status
```

## Sample Output

```json
{
  "use_case": "prior_auth_status",
  "patient": {"first_name": "John", "last_name": "Smith"},
  "procedure": "MRI lumbar spine",
  "service_date": "2026-04-05",
  "auth": {
    "status": "Certified — approved",
    "auth_number": "AUTH789012",
    "effective_date": "2026-03-28",
    "expiration_date": "2026-06-28"
  }
}
```

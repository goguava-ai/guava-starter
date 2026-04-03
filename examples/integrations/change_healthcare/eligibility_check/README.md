# Eligibility Check — Change Healthcare Integration

An inbound voice agent that accepts calls from patients wanting to verify their insurance coverage before an appointment. It collects identity and insurance information, submits a real-time 270 eligibility inquiry through Change Healthcare, and reads back the coverage status, copay, and deductible details.

## How It Works

**1. Accept the inbound call**

`accept_call()` picks up incoming calls. The agent collects the patient's name, date of birth, member ID, and insurance plan name.

**2. Submit a 270 eligibility inquiry**

`check_eligibility()` calls `POST /medicalnetwork/eligibility/v3` with subscriber and provider information. The request includes the service type code `30` (Health Benefit Plan Coverage) to check general coverage.

**3. Parse the 271 response**

`summarize_eligibility()` walks through the `benefitsInformation` array looking for:
- Code `1` — Active Coverage (plan name and group number)
- Code `C` — Copayment amount
- Code `G` — Deductible and remaining deductible balance

**4. Read coverage back to the patient**

If coverage is active, the agent reads the plan name, copay, and deductible. If coverage cannot be confirmed, the patient is directed to their insurance company.

## Change Healthcare API Calls

| Timing | Method | Endpoint | Purpose |
|---|---|---|---|
| Pre-call | `POST` | `/apip/auth/v2/token` | Obtain OAuth access token |
| Mid-call | `POST` | `/medicalnetwork/eligibility/v3` | Submit 270 real-time eligibility inquiry |

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
python -m examples.integrations.change_healthcare.eligibility_check
```

## Sample Output

```json
{
  "use_case": "eligibility_check",
  "patient": {"first_name": "Jane", "last_name": "Doe", "dob": "1985-06-15"},
  "member_id": "MBR123456",
  "insurance": "Blue Cross Blue Shield",
  "coverage": {
    "status": "active",
    "plan_name": "BCBS PPO Gold",
    "copay": "30",
    "deductible": "1500",
    "deductible_remaining": "800"
  }
}
```

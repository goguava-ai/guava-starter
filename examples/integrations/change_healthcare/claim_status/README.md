# Claim Status — Change Healthcare Integration

An inbound voice agent that looks up the status of a submitted insurance claim. Callers provide their member ID, date of birth, and approximate service date; the agent submits a 276 claim status inquiry through Change Healthcare and reads back the 277 response.

## How It Works

**1. Collect claim lookup details**

The agent gathers the patient's last name, date of birth, member ID, service date, and payer name.

**2. Submit a 276 claim status inquiry**

`get_claim_status()` posts to `POST /medicalnetwork/claimstatus/v3`. The payer ID maps to a specific insurance company via the Change Healthcare trading partner directory.

**3. Parse the 277 response**

`parse_claim_status()` reads the `claimStatusDetails` array and maps the status code to a human-readable description:
- `F0` — Finalized/Payment
- `F1` — Finalized/Denial
- `P1` / `P2` — Pending
- `R0` / `R3` — Returned to Provider

**4. Report status to the caller**

The agent reads the status, payer claim reference number, and adjudication date. For denials or returns, callers are advised that the billing team will review and follow up.

## Change Healthcare API Calls

| Timing | Method | Endpoint | Purpose |
|---|---|---|---|
| Pre-call | `POST` | `/apip/auth/v2/token` | Obtain OAuth access token |
| Mid-call | `POST` | `/medicalnetwork/claimstatus/v3` | Submit 276 claim status inquiry |

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
python -m examples.integrations.change_healthcare.claim_status
```

## Sample Output

```json
{
  "use_case": "claim_status",
  "patient_last_name": "Doe",
  "member_id": "MBR123456",
  "service_date": "2026-02-10",
  "payer": "Aetna",
  "claim_status": {
    "status_code": "F0",
    "status_description": "Finalized/Payment",
    "payer_claim_number": "AET2026021099",
    "adjudication_date": "2026-02-18"
  }
}
```

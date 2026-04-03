# Claim Submission Trigger — Change Healthcare Integration

An outbound voice agent that calls a contact to confirm billing and clinical details before submitting an 837P professional claim through Change Healthcare. If the contact confirms, the claim is submitted immediately during the call.

## How It Works

**1. Initiate an outbound call**

`create_outbound()` places the call. `reach_person()` ensures the agent is speaking with the right contact before proceeding.

**2. Confirm billing details**

The agent asks whether the visit information is accurate and whether insurance was active at the time of service. Any billing notes are also captured.

**3. Submit or hold**

- If confirmed: `submit_professional_claim()` posts an 837P payload to `POST /medicalnetwork/professionalclaims/v3` and the caller is given the claim reference ID.
- If there is an issue: the claim is held and flagged for billing team review.

**4. Build the 837P payload**

`build_claim_payload()` assembles the claim with subscriber info, provider NPI and tax ID, diagnosis and procedure codes, and service line details.

## Change Healthcare API Calls

| Timing | Method | Endpoint | Purpose |
|---|---|---|---|
| Pre-call | `POST` | `/apip/auth/v2/token` | Obtain OAuth access token |
| Post-confirm | `POST` | `/medicalnetwork/professionalclaims/v3` | Submit 837P professional claim |

## Setup

```bash
export GUAVA_AGENT_NUMBER="+1..."
export CHANGE_HEALTHCARE_CLIENT_ID="..."
export CHANGE_HEALTHCARE_CLIENT_SECRET="..."
export CHANGE_HEALTHCARE_TRADING_PARTNER_ID="000050"
export PROVIDER_NPI="1234567890"
export PROVIDER_TAX_ID="123456789"
# Demo claim data (replace with data from your EHR/billing system)
export DEMO_MEMBER_ID="MBR123456"
export DEMO_DIAGNOSIS_CODE="Z00.00"
export DEMO_PROCEDURE_CODE="99213"
export DEMO_SERVICE_DATE="2026-03-20"
export DEMO_CHARGE_AMOUNT="150.00"
export DEMO_PATIENT_DOB="1985-06-15"
```

## Run

```bash
python -m examples.integrations.change_healthcare.claim_submission_trigger \
  +15551234567 \
  --name "Jane Doe" \
  --appointment-id "APT-20260320-001"
```

## Sample Output

```json
{
  "appointment_id": "APT-20260320-001",
  "patient_name": "Jane Doe",
  "action": "claim_submitted",
  "claim_id": "20260320143022abc"
}
```

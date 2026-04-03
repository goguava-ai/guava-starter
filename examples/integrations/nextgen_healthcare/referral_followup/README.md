# Referral Followup

**Direction:** Outbound

Calls a patient who received a specialist referral to confirm receipt, check whether they've scheduled with the specialist, and identify any barriers. Logs the outreach outcome as a Communication resource in NextGen.

## What it does

1. Calls the patient and confirms receipt of the referral
2. Asks whether they've scheduled with the specialist and collects the appointment date if so
3. Captures any barriers (insurance, availability, access) if they haven't scheduled
4. Posts a `Communication` via `POST /Communication` to record the outreach outcome

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `NEXTGEN_BASE_URL` | NextGen FHIR R4 base URL |
| `NEXTGEN_TOKEN_URL` | OAuth token endpoint |
| `NEXTGEN_CLIENT_ID` | SMART on FHIR client ID |
| `NEXTGEN_CLIENT_SECRET` | SMART on FHIR client secret |

## Usage

```bash
python -m examples.integrations.nextgen_healthcare.referral_followup "+15551234567" --name "Jane Doe" --patient-id "pat-456" --referral-specialty "Cardiology"
```

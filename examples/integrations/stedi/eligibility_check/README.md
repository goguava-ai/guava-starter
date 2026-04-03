# Eligibility Check

**Direction:** Inbound

A patient calls ahead of an appointment to verify their insurance coverage is active. The agent collects their insurance card details, submits a real-time eligibility check (X12 270/271) to Stedi, and reads back whether their plan is active.

## What it does

1. Collects first name, last name, date of birth, member ID, and insurance company
2. Posts to `POST /change/medicalnetwork/eligibility/v3` with service type code `30` (Health Benefit Plan Coverage)
3. Parses `planStatus[].statusCode` — `"1"` = active, `"6"` = inactive
4. Reads back the result and guides the patient on next steps if coverage is not confirmed

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `STEDI_API_KEY` | Stedi API key |
| `STEDI_PROVIDER_NPI` | Provider NPI number |
| `STEDI_PROVIDER_NAME` | Provider organization name (optional) |

## Usage

```bash
python -m examples.integrations.stedi.eligibility_check
```

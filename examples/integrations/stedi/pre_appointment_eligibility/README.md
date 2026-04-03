# Pre-Appointment Eligibility

**Direction:** Outbound

The day before an appointment, this agent calls the patient to confirm their insurance is still active. If coverage checks out, the call is a brief confirmation. If coverage is inactive, the agent explains the situation and collects how the patient wants to proceed.

## What it does

1. Runs a real-time eligibility check pre-call via `POST /change/medicalnetwork/eligibility/v3` using the patient's insurance details
2. Parses `planStatus[].statusCode` to determine if coverage is active (`"1"`) or inactive (`"6"`)
3. **If active:** Calls the patient, confirms the appointment, and lets them know coverage looks good
4. **If inactive:** Calls the patient, explains the coverage issue, and collects their preferred resolution (contact insurer, bring alternate card, self-pay, or billing callback)
5. **If check inconclusive:** Still calls to confirm the appointment and asks the patient to bring their card

Voicemails adapt to the eligibility result: active coverage gets a brief confirmation; inactive coverage gets a brief heads-up.

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `STEDI_API_KEY` | Stedi API key |
| `STEDI_PROVIDER_NPI` | Provider NPI number |
| `STEDI_PROVIDER_NAME` | Provider organization name (optional) |

## Usage

```bash
python -m examples.integrations.stedi.pre_appointment_eligibility \
  "+15551234567" \
  --name "Jane Doe" \
  --first-name Jane \
  --last-name Doe \
  --dob 1985-03-15 \
  --member-id XYZ123456 \
  --payer-id BCBS \
  --appointment-date "March 27th at 2:00 PM"
```

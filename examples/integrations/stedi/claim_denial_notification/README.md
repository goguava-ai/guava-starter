# Claim Denial Notification

**Direction:** Outbound

When a claim is denied, this agent proactively calls the patient to notify them, explain the denial, and help them choose a next step — filing an appeal, having billing review the claim, setting up a payment plan, or requesting a specialist callback.

## What it does

1. Checks claim status pre-call via `POST /change/medicalnetwork/claimstatus/v2`
2. Inspects `statusCategoryCode` for denial codes: `A6` (rejected), `A7` (denied), or `F4` (finalized — denied)
3. **If denied:** Places the call, informs the patient, and collects their preferred next step
4. **If not denied:** Places a brief call to let the patient know the denial may have been resolved and that billing will follow up
5. Voicemails are non-alarming and ask the patient to call back to discuss next steps

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `STEDI_API_KEY` | Stedi API key |
| `STEDI_PROVIDER_NPI` | Provider NPI number |
| `STEDI_PROVIDER_NAME` | Provider organization name (optional) |

## Usage

```bash
python -m examples.integrations.stedi.claim_denial_notification \
  "+15551234567" \
  --name "Jane Doe" \
  --first-name Jane \
  --last-name Doe \
  --dob 1985-03-15 \
  --member-id XYZ123456 \
  --payer-id BCBS \
  --claim-number 100001 \
  --service "your March 10th office visit"
```

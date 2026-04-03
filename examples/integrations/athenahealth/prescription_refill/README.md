# Prescription Refill

**Direction:** Outbound

Calls a patient to confirm a prescription refill request. Collects their preferred pharmacy and any new symptoms, then submits the refill request to the patient chart in Athenahealth.

## What it does

1. Calls the patient to confirm they still need the refill
2. Checks for any new or worsening symptoms
3. Collects preferred pharmacy name and location
4. Submits a refill request via `POST /v1/{practiceId}/patients/{patientId}/medications`

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `ATHENA_CLIENT_ID` | Athenahealth OAuth client ID |
| `ATHENA_CLIENT_SECRET` | Athenahealth OAuth client secret |
| `ATHENA_PRACTICE_ID` | Practice identifier |

## Usage

```bash
python -m examples.integrations.athenahealth.prescription_refill "+15551234567" --name "Jane Doe" --patient-id "67890" --medication "Lisinopril 10mg"
```

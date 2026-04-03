# Insurance Verification

**Direction:** Outbound

Calls a patient before their visit to verify insurance information. Fetches the current insurance on file so the agent can confirm rather than re-collect. Posts updated insurance to Athenahealth if it has changed.

## What it does

1. Fetches insurance on file via `GET /v1/{practiceId}/patients/{patientId}/insurances`
2. Calls the patient and presents the current insurance for confirmation
3. If insurance changed: collects new provider, member ID, and group number
4. Posts updated insurance via `POST /v1/{practiceId}/patients/{patientId}/insurances`

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `ATHENA_CLIENT_ID` | Athenahealth OAuth client ID |
| `ATHENA_CLIENT_SECRET` | Athenahealth OAuth client secret |
| `ATHENA_PRACTICE_ID` | Practice identifier |

## Usage

```bash
python -m examples.integrations.athenahealth.insurance_verification "+15551234567" --name "Jane Doe" --patient-id "67890"
```

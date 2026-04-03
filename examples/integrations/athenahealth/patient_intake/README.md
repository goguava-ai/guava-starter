# Patient Intake

**Direction:** Outbound

Calls a patient ahead of their appointment to complete pre-visit intake. Fetches medications and allergies on file from Athenahealth before the call so the agent confirms rather than re-collects. Posts an intake summary back to the patient chart when the call completes.

## What it does

1. Fetches current medications via `GET /v1/{practiceId}/patients/{patientId}/medications`
2. Fetches known allergies via `GET /v1/{practiceId}/patients/{patientId}/allergies`
3. Calls the patient and collects chief complaint, medication/allergy updates, and recent changes
4. Posts an intake summary document to the chart via `POST /v1/{practiceId}/patients/{patientId}/documents`

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `ATHENA_CLIENT_ID` | Athenahealth OAuth client ID |
| `ATHENA_CLIENT_SECRET` | Athenahealth OAuth client secret |
| `ATHENA_PRACTICE_ID` | Practice identifier |

## Usage

```bash
python -m examples.integrations.athenahealth.patient_intake "+15551234567" --name "Jane Doe" --patient-id "67890" --appointment "Friday at 2:00 PM"
```

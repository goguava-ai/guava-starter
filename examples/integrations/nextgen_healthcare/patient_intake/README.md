# Patient Intake

**Direction:** Outbound

Calls a patient ahead of their appointment to complete pre-visit intake. Fetches active medications and allergies from the NextGen FHIR API before the call. Posts an intake summary as a DocumentReference when complete.

## What it does

1. Fetches active medications via `GET /MedicationRequest?patient={id}&status=active`
2. Fetches allergies via `GET /AllergyIntolerance?patient={id}`
3. Calls the patient and collects chief complaint, confirms meds/allergies, notes changes
4. Posts intake note via `POST /DocumentReference`

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
python -m examples.integrations.nextgen_healthcare.patient_intake "+15551234567" --name "Jane Doe" --patient-id "pat-456" --appointment "Thursday at 3:30 PM"
```

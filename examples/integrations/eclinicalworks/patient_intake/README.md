# Patient Intake

**Direction:** Outbound

Calls a patient ahead of their appointment to complete pre-visit intake. Fetches current medications and allergies from the eClinicalWorks FHIR API before the call so the agent can confirm rather than re-collect. Posts an intake summary as a DocumentReference when complete.

## What it does

1. Fetches medications via `GET /MedicationStatement?patient={id}`
2. Fetches allergies via `GET /AllergyIntolerance?patient={id}`
3. Calls the patient to collect chief complaint, confirm meds/allergies, and note changes
4. Posts intake note via `POST /DocumentReference`

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `ECW_BASE_URL` | eClinicalWorks FHIR R4 base URL |
| `ECW_TOKEN_URL` | OAuth token endpoint |
| `ECW_CLIENT_ID` | SMART on FHIR client ID |
| `ECW_CLIENT_SECRET` | SMART on FHIR client secret |

## Usage

```bash
python -m examples.integrations.eclinicalworks.patient_intake "+15551234567" --name "Jane Doe" --patient-id "pat-456" --appointment "Monday at 10:00 AM"
```

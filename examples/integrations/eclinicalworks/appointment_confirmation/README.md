# Appointment Confirmation

**Direction:** Outbound

Calls a patient to confirm an upcoming appointment. Reads appointment details from the eClinicalWorks FHIR API and patches the status to `cancelled` if the patient cannot attend.

## What it does

1. Fetches appointment via `GET /Appointment/{id}`
2. Calls the patient and reads back date, time, and provider from the FHIR resource
3. If the patient cancels: patches status to `cancelled` via `PATCH /Appointment/{id}`

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
python -m examples.integrations.eclinicalworks.appointment_confirmation "+15551234567" --name "Jane Doe" --appointment-id "apt-abc123"
```

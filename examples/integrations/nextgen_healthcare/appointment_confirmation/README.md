# Appointment Confirmation

**Direction:** Outbound

Calls a patient to confirm an upcoming appointment stored in NextGen Healthcare. Patches the appointment status to `cancelled` in the NextGen FHIR API if the patient cannot attend.

## What it does

1. Fetches appointment details via `GET /Appointment/{id}`
2. Reads back date, time, type, and provider from the FHIR resource
3. If cancelled: patches status via `PATCH /Appointment/{id}` with a JSON-patch body

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
python -m examples.integrations.nextgen_healthcare.appointment_confirmation "+15551234567" --name "Jane Doe" --appointment-id "apt-123"
```

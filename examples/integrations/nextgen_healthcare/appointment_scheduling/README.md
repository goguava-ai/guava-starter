# Appointment Scheduling

**Direction:** Inbound

A patient calls to schedule an appointment. The agent collects their identity and preferences, searches NextGen for a free slot, presents the time, and books an Appointment resource on confirmation.

## What it does

1. Collects patient name, DOB, reason for visit, and preferred date
2. Looks up the patient via `GET /Patient?family=...&birthdate=...`
3. Searches free slots via `GET /Slot?start=ge{date}&status=free`
4. Presents the first available slot and, on confirmation, books via `POST /Appointment`

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
python -m examples.integrations.nextgen_healthcare.appointment_scheduling
```

# Appointment Scheduling

**Direction:** Inbound

A patient calls to schedule an appointment. The agent collects their identity and scheduling preferences, searches Athenahealth for an available slot, presents a time, and books it upon confirmation.

## What it does

1. Collects patient name, DOB, reason for visit, and preferred date/time
2. Looks up the patient record via `GET /v1/{practiceId}/patients?lastname=...&dob=...`
3. Searches for open slots via `GET /v1/{practiceId}/appointments/open`
4. Presents the first available slot and asks for confirmation
5. Books the slot via `PUT /v1/{practiceId}/appointments/{appointmentId}`

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `ATHENA_CLIENT_ID` | Athenahealth OAuth client ID |
| `ATHENA_CLIENT_SECRET` | Athenahealth OAuth client secret |
| `ATHENA_PRACTICE_ID` | Practice identifier |
| `ATHENA_APPOINTMENT_TYPE_ID` | Default appointment type ID |

## Usage

```bash
python -m examples.integrations.athenahealth.appointment_scheduling
```

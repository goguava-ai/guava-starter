# Appointment Confirmation

**Direction:** Outbound

Calls a patient to confirm an upcoming appointment. If they can't make it, the agent cancels the appointment in Athenahealth and offers to have the office call back to reschedule.

## What it does

1. Fetches appointment details via `GET /v1/{practiceId}/appointments/{appointmentId}`
2. Calls the patient and presents date, time, type, and provider
3. If the patient cancels: updates status to `x` (cancelled) via `PUT /v1/{practiceId}/appointments/{appointmentId}`

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `ATHENA_CLIENT_ID` | Athenahealth OAuth client ID |
| `ATHENA_CLIENT_SECRET` | Athenahealth OAuth client secret |
| `ATHENA_PRACTICE_ID` | Practice identifier |

## Usage

```bash
python -m examples.integrations.athenahealth.appointment_confirmation "+15551234567" --name "Jane Doe" --appointment-id "12345"
```

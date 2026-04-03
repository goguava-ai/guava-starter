# Appointment Reminder

**Direction:** Outbound

Calls a client to remind them of an upcoming appointment and confirm attendance. If they can't make it, the agent cancels the appointment in Acuity.

## What it does

1. Fetches appointment details via `GET /appointments/{id}`
2. Calls the client and reads back date, time, type, and provider
3. If they cancel: cancels via `PUT /appointments/{id}/cancel`
4. Handles reschedule intent by directing clients to the website or callbacks

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `ACUITY_USER_ID` | Acuity numeric User ID |
| `ACUITY_API_KEY` | Acuity API Key |

## Usage

```bash
python -m examples.integrations.acuity_scheduling.appointment_reminder "+15551234567" --name "Alex Rivera" --appointment-id "987654321"
```

# Appointment Reschedule

**Direction:** Inbound

A client calls to move their existing appointment to a new time. The agent looks up availability on their preferred date and reschedules the original appointment via the Acuity API.

## What it does

1. Loads the existing appointment via `GET /appointments/{id}`
2. Collects the client's preferred new date
3. Searches availability via `GET /availability/times`
4. Presents the first open slot and, on confirmation, reschedules via `PUT /appointments/{id}/reschedule`

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `ACUITY_USER_ID` | Acuity numeric User ID |
| `ACUITY_API_KEY` | Acuity API Key |

## Usage

```bash
python -m examples.integrations.acuity_scheduling.appointment_reschedule
```

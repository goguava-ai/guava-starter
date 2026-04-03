# Appointment Reminder

**Direction:** Outbound

Crestwood Wellness proactively calls clients ahead of their upcoming appointments. The agent confirms attendance, handles cancellation requests in-call, and notes reschedule requests for follow-up.

## What it does

1. Fetches the appointment details pre-call via `GET /v2/bookings/{booking_id}` (start time, duration)
2. Reaches the client by name; leaves a voicemail if unavailable
3. Confirms whether the client is attending, needs to cancel, or needs to reschedule
4. If cancelling in-call: calls `POST /v2/bookings/{booking_id}/cancel` with the current booking version
5. If rescheduling: notes the request and directs the client to call back or book online

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `SQUARE_ACCESS_TOKEN` | Square access token from the Developer Dashboard |
| `SQUARE_LOCATION_ID` | Your Square location ID |

## Usage

```bash
python -m examples.integrations.square_appointments.appointment_reminder \
  "+15551234567" \
  --booking-id "booking_abc123" \
  --name "Alex Rivera"
```

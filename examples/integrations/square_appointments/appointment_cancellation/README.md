# Appointment Cancellation & Rescheduling

**Direction:** Inbound

A client calls Crestwood Wellness to cancel or reschedule an existing appointment. The agent verifies the booking by ID, confirms the caller's identity via email, and processes the cancellation or reschedule via the Square Bookings API.

## What it does

1. Collects the booking ID and customer email for verification
2. Fetches the booking via `GET /v2/bookings/{booking_id}` to confirm it exists and is active
3. For **cancellation**: calls `POST /v2/bookings/{booking_id}/cancel` with the current booking version
4. For **rescheduling**: calls `PUT /v2/bookings/{booking_id}` with a new `start_at` timestamp constructed from the caller's preferred date and time of day
5. Confirms the outcome to the caller

> **Note:** New appointment times for rescheduling are constructed from the caller's freeform date input mapped to a fixed hour (morning = 09:00, afternoon = 14:00, evening = 16:00). In production, validate against `POST /v2/bookings/availability/search` before updating.

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `SQUARE_ACCESS_TOKEN` | Square access token from the Developer Dashboard |
| `SQUARE_LOCATION_ID` | Your Square location ID |
| `SQUARE_SERVICE_VARIATION_ID` | The catalog item variation ID for the service |
| `SQUARE_TEAM_MEMBER_ID` | The team member ID associated with the bookings |

## Usage

```bash
python -m examples.integrations.square_appointments.appointment_cancellation
```

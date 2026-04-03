# Appointment Booking

**Direction:** Inbound

A client calls to book a new appointment. The agent collects their information and preferences, searches Acuity for availability, presents a time, and creates the booking on confirmation.

## What it does

1. Pre-loads appointment types via `GET /appointment-types`
2. Collects name, email, phone, service type, and preferred date
3. Searches availability via `GET /availability/times?appointmentTypeID=...&date=...`
4. Falls back to the following day if the preferred date has no openings
5. Creates the appointment via `POST /appointments` on confirmation

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `ACUITY_USER_ID` | Acuity numeric User ID |
| `ACUITY_API_KEY` | Acuity API Key |
| `ACUITY_APPOINTMENT_TYPE_ID` | Default appointment type ID |

## Usage

```bash
python -m examples.integrations.acuity_scheduling.appointment_booking
```

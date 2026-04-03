# Appointment Booking

**Direction:** Inbound

A client calls Crestwood Wellness to book an appointment. The agent collects their contact details and preferences, looks up or creates their Square customer record, and creates a confirmed booking via the Square Bookings API.

## What it does

1. Collects name, email, phone, service type, preferred date, preferred time of day, and any special requests
2. Searches for an existing customer via `POST /v2/customers/search` (email lookup)
3. Creates a new customer via `POST /v2/customers` if none is found
4. Constructs a start time from the caller's preferred date and time-of-day preference
5. Creates the booking via `POST /v2/bookings` with the customer ID and appointment segment
6. Reads back the booking confirmation ID to the caller

> **Note:** Appointment start times are constructed from the caller's freeform date input mapped to a fixed hour (morning = 09:00, afternoon = 14:00, evening = 16:00). In production, replace this with a call to `POST /v2/bookings/availability/search` to resolve a real open slot.

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `SQUARE_ACCESS_TOKEN` | Square access token from the Developer Dashboard |
| `SQUARE_LOCATION_ID` | Your Square location ID |
| `SQUARE_SERVICE_VARIATION_ID` | The catalog item variation ID for the service being booked |
| `SQUARE_TEAM_MEMBER_ID` | The team member (staff) ID to assign the appointment to |

## Usage

```bash
python -m examples.integrations.square_appointments.appointment_booking
```

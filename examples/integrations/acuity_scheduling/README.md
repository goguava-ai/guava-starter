# Acuity Scheduling Integration

Voice agents that integrate with the [Acuity Scheduling API](https://developers.acuityscheduling.com) to book, confirm, reschedule, and follow up on appointments — for wellness clinics, salons, fitness studios, and any service business running on Acuity.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`appointment_booking`](appointment_booking/) | Inbound | Client calls to book a new appointment; agent finds availability and confirms |
| [`appointment_reminder`](appointment_reminder/) | Outbound | Remind clients of upcoming appointments; confirm attendance or offer to cancel |
| [`appointment_reschedule`](appointment_reschedule/) | Inbound | Client calls to move an existing appointment to a new time |
| [`no_show_followup`](no_show_followup/) | Outbound | Follow up after a missed appointment; offer to rebook |
| [`availability_check`](availability_check/) | Inbound | Client calls to ask when the next available slot is |

## Authentication

All examples use HTTP Basic Auth with your Acuity User ID and API Key:

```python
import os
AUTH = (os.environ["ACUITY_USER_ID"], os.environ["ACUITY_API_KEY"])
```

Find your User ID and API Key under **Integrations → API** in the Acuity Scheduling dashboard.

## Base URL

```
https://acuityscheduling.com/api/v1/
```

## Common Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `ACUITY_USER_ID` | Your numeric Acuity User ID |
| `ACUITY_API_KEY` | Your Acuity API Key |
| `ACUITY_APPOINTMENT_TYPE_ID` | Default appointment type ID (optional) |

## Usage

```bash
export GUAVA_AGENT_NUMBER="+1..."
export ACUITY_USER_ID="12345"
export ACUITY_API_KEY="..."
```

Outbound examples:

```bash
python -m examples.integrations.acuity_scheduling.appointment_reminder "+15551234567" --name "Alex Rivera" --appointment-id "987654321"
python -m examples.integrations.acuity_scheduling.no_show_followup "+15551234567" --name "Alex Rivera" --appointment-id "987654321"
```

Inbound examples:

```bash
python -m examples.integrations.acuity_scheduling.appointment_booking
python -m examples.integrations.acuity_scheduling.appointment_reschedule
python -m examples.integrations.acuity_scheduling.availability_check
```

## Acuity Scheduling API Reference

- [Appointments](https://developers.acuityscheduling.com/reference/appointments)
- [Availability](https://developers.acuityscheduling.com/reference/availability)
- [Clients](https://developers.acuityscheduling.com/reference/clients)
- [Appointment Types](https://developers.acuityscheduling.com/reference/appointment-types)

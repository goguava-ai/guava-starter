# Appointment Scheduling

**Direction:** Inbound

An inbound voice agent that picks up when a patient calls Valley General Hospital to schedule an appointment or procedure. The agent collects patient identity and scheduling preferences, searches Meditech Expanse for available slots in real time, presents a time to the patient, and books the appointment on confirmation — all within a single phone call.

## What it does

1. Answers inbound calls to the hospital's scheduling line.
2. Collects first name, last name, date of birth, appointment type (primary care visit, specialist consult, outpatient procedure, radiology, or lab work), preferred date, and morning/afternoon preference.
3. Looks up the patient in Meditech Expanse (`GET /Patient`) by last name and date of birth to retrieve their FHIR resource ID.
4. Searches for free slots (`GET /Slot`) on or after the preferred date, applying time-of-day filtering when possible.
5. Presents the best available slot to the patient and collects a yes/no confirmation.
6. If confirmed: POSTs an `Appointment` resource to Meditech Expanse linking the patient and slot.
7. If no slots are found or the patient declines: closes the call and advises that a scheduling coordinator will follow up within one business day.

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Phone number assigned to the Guava voice agent (E.164 format) |
| `MEDITECH_FHIR_BASE_URL` | Meditech Expanse FHIR R4 base URL (e.g. `https://fhir.meditech.com/r4`) |
| `MEDITECH_ACCESS_TOKEN` | OAuth 2.0 bearer token for the Meditech Expanse FHIR API |

## Usage

```bash
export GUAVA_AGENT_NUMBER="+1..."
export MEDITECH_FHIR_BASE_URL="https://fhir.meditech.com/r4"
export MEDITECH_ACCESS_TOKEN="..."

python __main__.py
```

The agent listens for inbound calls. Each call is handled by a new `AppointmentSchedulingController` instance.

## Meditech FHIR Calls

| Timing | Method | Resource | Purpose |
|---|---|---|---|
| Mid-call | `GET` | `Patient` | Look up patient FHIR ID by last name and date of birth |
| Mid-call | `GET` | `Slot` | Find available free slots on or after the preferred date |
| Post-confirm | `POST` | `Appointment` | Book the selected slot and link it to the patient record |

## Sample Output

Two JSON blobs are printed to stdout: one after preferences are collected, one after the appointment is booked.

```json
{
  "use_case": "appointment_scheduling",
  "phase": "preferences_collected",
  "fields": {
    "first_name": "Jane",
    "last_name": "Doe",
    "appointment_type": "radiology",
    "preferred_date": "2026-04-10",
    "time_of_day_preference": "morning"
  }
}
```

```json
{
  "use_case": "appointment_scheduling",
  "phase": "booked",
  "patient_fhir_id": "PT-00421",
  "slot_id": "SL-88712",
  "appointment_start": "2026-04-10T09:15:00Z"
}
```

# Appointment Scheduling — Epic Integration

An inbound voice agent that picks up when a patient calls to book an appointment. It collects their identity and preferences, searches Epic for available slots in real time, presents a time to the patient, and books the appointment on confirmation — all within a single phone call.

## How It Works

**1. Accept the inbound call**

`accept_call()` picks up incoming calls to the agent number. `set_task()` starts collecting patient information and scheduling preferences.

**2. Collect patient identity and preferences**

The first task gathers:
- First and last name
- Date of birth (used to look up the Epic patient record)
- Appointment type (annual physical, sick visit, etc.)
- Preferred date and time of day

**3. Mid-call: look up the patient and search for slots**

Once preferences are collected, `search_availability()` makes two Epic calls in sequence:
- `GET /Patient` — searches by last name and date of birth to find the patient's FHIR resource ID
- `GET /Slot` — searches for free slots on or after the preferred date matching the appointment type

**4. Present a slot and get confirmation**

If a slot is found, its start time is formatted and spoken to the patient ("I found an opening on Thursday, March 27 at 9:00 AM — would that work?"). A second `set_task()` collects the patient's yes/no response.

**5. Book or gracefully decline**

- If the patient confirms: `POST /Appointment` books the slot in Epic, linking the patient FHIR ID and slot reference.
- If they decline, or no slots were found: the agent lets the patient know a scheduling coordinator will call back within one business day.

## Epic FHIR Calls

| Timing | Method | Resource | Purpose |
|---|---|---|---|
| Mid-call | `GET` | `Patient` | Look up patient FHIR ID by name and date of birth |
| Mid-call | `GET` | `Slot` | Find available appointment slots near the preferred date |
| Post-confirm | `POST` | `Appointment` | Book the selected slot for the patient |

## Setup

```bash
export GUAVA_AGENT_NUMBER="+1..."
export EPIC_BASE_URL="https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4"
export EPIC_ACCESS_TOKEN="..."
```

## Run

This example is inbound — start the listener and patients call in:

```bash
python -m examples.integrations.epic.appointment_scheduling
```

## Sample Output

Two JSON blobs are printed: one after preferences are collected, one after booking:

```json
{
  "use_case": "appointment_scheduling",
  "phase": "preferences_collected",
  "fields": {
    "first_name": "Jane",
    "last_name": "Doe",
    "appointment_type": "annual physical",
    "preferred_date": "2026-03-25"
  }
}
```

```json
{
  "use_case": "appointment_scheduling",
  "phase": "booked",
  "patient_fhir_id": "pat456",
  "slot_id": "slot789",
  "appointment_start": "2026-03-25T09:00:00Z"
}
```

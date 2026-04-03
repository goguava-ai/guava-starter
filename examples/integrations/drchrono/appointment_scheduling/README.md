# Appointment Scheduling

**Direction:** Inbound

A patient calls to schedule an appointment at Oakridge Family Medicine. The agent collects their email to look up or create their patient record, gathers scheduling preferences, and creates an appointment in DrChrono. The scheduling team is notified to confirm the exact time.

## What it does

1. Collects patient email and looks up their record via `GET /patients?email={email}`
2. If no record is found, collects name and date of birth, then creates the patient via `POST /patients`
3. Collects appointment reason, preferred date, time of day, and appointment type
4. Creates an appointment record via `POST /appointments` with a placeholder scheduled time
5. Informs the caller that the scheduling team will confirm the exact time by phone

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `DRCHRONO_ACCESS_TOKEN` | DrChrono OAuth2 Bearer token |
| `DRCHRONO_DOCTOR_ID` | Integer ID of the doctor to assign appointments to |
| `DRCHRONO_OFFICE_ID` | Integer ID of the office |

## Usage

```bash
export GUAVA_AGENT_NUMBER="+1..."
export DRCHRONO_ACCESS_TOKEN="..."
export DRCHRONO_DOCTOR_ID="123"
export DRCHRONO_OFFICE_ID="456"

python -m examples.integrations.drchrono.appointment_scheduling
```

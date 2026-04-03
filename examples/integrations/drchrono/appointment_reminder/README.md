# Appointment Reminder

**Direction:** Outbound

Proactively calls a patient to remind them of an upcoming appointment. The agent confirms attendance, collects any questions to pass along to the care team, and updates the appointment status in DrChrono accordingly.

## What it does

1. Fetches appointment details (scheduled time, reason, duration) via `GET /appointments/{appointment_id}`
2. Calls the patient and presents the appointment details
3. Collects confirmation status: confirmed, need-to-reschedule, or cancel
4. Updates appointment status via `PATCH /appointments/{appointment_id}`
5. Logs the call via `POST /call_logs`

## HIPAA Note

This agent calls patients about their health appointments. Do not share any PHI in voicemails beyond the caller's name and the practice name. Identity is confirmed via the `reach_person` step before any appointment details are discussed.

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `DRCHRONO_ACCESS_TOKEN` | DrChrono OAuth2 Bearer token |
| `DRCHRONO_DOCTOR_ID` | Integer ID of the doctor (used for call log attribution) |
| `DRCHRONO_OFFICE_ID` | Integer ID of the office |

## Usage

```bash
export GUAVA_AGENT_NUMBER="+1..."
export DRCHRONO_ACCESS_TOKEN="..."
export DRCHRONO_DOCTOR_ID="123"
export DRCHRONO_OFFICE_ID="456"

python -m examples.integrations.drchrono.appointment_reminder "+15551234567" --appointment-id "98765" --name "Jane Doe" --patient-id "42"
```

# Appointment Confirmation — Epic Integration

An outbound voice agent that calls patients to confirm or cancel upcoming appointments, then immediately patches the appointment status back into Epic via FHIR.

## How It Works

**1. Before the call — fetch appointment details from Epic**

The controller's `__init__` makes a `GET /Appointment/{id}` request to Epic. If the fetch succeeds, it parses the `start` timestamp and formats it into a human-readable string (e.g. "Tuesday, March 25 at 10:00 AM") that the agent can speak naturally.

**2. Reach the patient**

`reach_person()` handles gatekeepers, voicemail detection, and live-answer verification so the task only starts when a real person picks up. If the patient can't be reached, the agent leaves a voicemail asking them to call back.

**3. Confirm or cancel**

The agent presents the appointment time and collects two fields:
- `confirmation` — "confirm" or "cancel"
- `cancellation_reason` — captured only if they cancel

**4. After the call — write the result back to Epic**

`save_results()` sends a `PATCH /Appointment/{id}` to Epic with `status: "booked"` or `status: "cancelled"`. If the patient cancelled and gave a reason, it's included in the `comment` field. The call ends with a branch based on the outcome.

## Epic FHIR Calls

| Timing | Method | Resource | Purpose |
|---|---|---|---|
| Pre-call | `GET` | `Appointment/{id}` | Fetch appointment start time for personalized greeting |
| Post-call | `PATCH` | `Appointment/{id}` | Update appointment status to `booked` or `cancelled` |

## Setup

```bash
export GUAVA_AGENT_NUMBER="+1..."
export EPIC_BASE_URL="https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4"
export EPIC_ACCESS_TOKEN="..."
```

## Run

```bash
python -m examples.integrations.epic.appointment_confirmation \
  "+15551234567" \
  --name "Jane Doe" \
  --appointment-id "abc123"
```

## Sample Output

After the call completes, results are printed as JSON and the Epic appointment record is patched:

```json
{
  "use_case": "appointment_confirmation",
  "patient_name": "Jane Doe",
  "appointment_id": "abc123",
  "fields": {
    "confirmation": "confirm",
    "cancellation_reason": null
  }
}
```

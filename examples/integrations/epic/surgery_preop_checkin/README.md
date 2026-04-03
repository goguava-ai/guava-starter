# Surgery Pre-Op Checkin — Epic Integration

An outbound voice agent that calls patients the day before surgery to complete a pre-operative checklist by phone. Responses are saved to Epic as a `DocumentReference` (nurse pre-operative assessment note) so the surgical team has a complete readiness record before the patient arrives.

## How It Works

**1. Reach the patient**

`reach_person()` confirms the patient is on the line. If unreachable, an urgent voicemail is left asking them to call back as soon as possible to complete their pre-op checklist before their procedure.

**2. Complete the pre-op checklist**

The agent works through four required readiness checks:
- `npo_confirmed` — has the patient fasted since midnight (no food or water)?
- `bowel_prep_completed` — was bowel prep completed as instructed, or was it not required?
- `transport_arranged` — has a responsible adult arranged to drive them home?
- `medications_held` — have blood thinners, diabetes medications, or other hold-listed drugs been paused?

Plus an optional `questions` field for anything the patient wants the surgical team to know.

**3. After the call — post a DocumentReference to Epic**

`save_results()` encodes the checklist responses as a plain-text note, then posts it as a `DocumentReference` (LOINC `34745-0`, Nurse pre-operative assessment note) attached to the patient record. The surgical team can pull this note directly from Epic before the procedure.

**4. Risk-based close**

The agent checks for two critical failures before closing:
- NPO not confirmed (patient ate or drank) → instructs them to call the surgical team immediately, as this may affect whether surgery can proceed.
- Transport not arranged → same urgency.

If all checks pass, the patient is cleared and reminded of their arrival time.

## Epic FHIR Calls

| Timing | Method | Resource | Purpose |
|---|---|---|---|
| Post-call | `POST` | `DocumentReference` | Save pre-op checklist as a nurse assessment note in the patient record |

## Setup

```bash
export GUAVA_AGENT_NUMBER="+1..."
export EPIC_BASE_URL="https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4"
export EPIC_ACCESS_TOKEN="..."
```

## Run

```bash
python -m examples.integrations.epic.surgery_preop_checkin \
  "+15551234567" \
  --name "Jane Doe" \
  --patient-id "pat456" \
  --surgery-date "March 20th at 7:00 AM"
```

## Sample Output

```json
{
  "use_case": "surgery_preop_checkin",
  "patient_name": "Jane Doe",
  "surgery_date": "March 20th at 7:00 AM",
  "fields": {
    "npo_confirmed": "yes",
    "bowel_prep_completed": "not required",
    "transport_arranged": "yes",
    "medications_held": "yes",
    "questions": "Will I be able to keep my hearing aids in during surgery?"
  }
}
```

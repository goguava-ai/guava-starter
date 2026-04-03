# Patient Intake — Epic Integration

An outbound voice agent that calls patients before their appointment to complete pre-visit intake. It fetches the patient's existing medications and allergies from Epic beforehand, so the agent can confirm existing records rather than asking the patient to recite them from scratch.

## How It Works

**1. Before the call — pre-load clinical context from Epic**

The controller fetches two resources for the patient before dialing:
- `GET /AllergyIntolerance` — active allergies on file
- `GET /MedicationStatement` — active medications on file

These lists are stored and used to dynamically shape the intake questions. If either fetch fails, the call proceeds normally with open-ended questions.

**2. Reach the patient**

`reach_person()` ensures the task only starts when the patient (not a gatekeeper or voicemail) answers. If unreachable, a voicemail is left asking them to call back.

**3. Dynamic intake questions**

`begin_intake()` builds the checklist at runtime:
- If medications are on file, the agent reads the list back and asks the patient to confirm or correct it — saving time and reducing re-collection friction.
- If no medications are on file, the agent asks from scratch.
- Same logic applies for allergies.

The checklist also collects:
- `chief_complaint` — the main reason for the visit
- `recent_health_changes` — any new symptoms or hospitalizations since the last visit

**4. After the call — post intake note to Epic**

`save_results()` encodes the full intake summary as a base64 text attachment and posts it as a `DocumentReference` (LOINC code `34117-2`, History and Physical Note) linked to the patient. The care team can review it in Epic before the appointment.

## Epic FHIR Calls

| Timing | Method | Resource | Purpose |
|---|---|---|---|
| Pre-call | `GET` | `AllergyIntolerance` | Fetch active allergies to confirm rather than re-collect |
| Pre-call | `GET` | `MedicationStatement` | Fetch active medications to confirm rather than re-collect |
| Post-call | `POST` | `DocumentReference` | Save intake note for care team review before the visit |

## Setup

```bash
export GUAVA_AGENT_NUMBER="+1..."
export EPIC_BASE_URL="https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4"
export EPIC_ACCESS_TOKEN="..."
```

## Run

```bash
python -m examples.integrations.epic.patient_intake \
  "+15551234567" \
  --name "Jane Doe" \
  --patient-id "pat456" \
  --appointment "Friday at 2:00 PM"
```

## Sample Output

```json
{
  "use_case": "patient_intake",
  "patient_name": "Jane Doe",
  "prior_record": {
    "medications_on_file": ["Metformin 500mg", "Lisinopril 10mg"],
    "allergies_on_file": ["Penicillin"]
  },
  "fields": {
    "chief_complaint": "Persistent fatigue and occasional dizziness",
    "current_medications": "Same as on file, confirmed accurate",
    "allergies": "Same as on file, confirmed",
    "recent_health_changes": "None reported"
  }
}
```

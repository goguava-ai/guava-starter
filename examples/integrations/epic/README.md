# Epic EHR Integration Examples

These examples show how Guava voice agents integrate with Epic — the dominant EHR system in US healthcare — reading and writing patient data via the Epic FHIR R4 API across 10 clinical use cases.

## Common Pattern

Each example extends the standard Guava `CallController` pattern by adding Epic FHIR API calls at strategic points. All API calls are wrapped in `try/except` so the Guava call completes gracefully even if the Epic API is unreachable. Three integration patterns are demonstrated:

1. **Pre-call GET** — Fetch patient context from Epic before the call to personalize the conversation or adjust the checklist (e.g., `chronic_disease_monitoring` fetches active Conditions to decide which vitals to collect; `patient_intake` fetches allergies and medications on file so the agent confirms rather than re-collects).
2. **Post-call POST** — Push collected data to Epic in `save_results()` after the conversation completes (e.g., `post_discharge_followup` posts an Observation; `insurance_update` creates a Coverage).
3. **Mid-call search + book** — Query Epic during the call to drive a multi-step flow (e.g., `appointment_scheduling` collects preferences, searches for available Slots, presents a time to the patient, and books on confirmation).

## Examples

| Use Case | Pattern | Scenario | Epic FHIR Resource |
|---|---|---|---|
| **appointment_confirmation** | Outbound | Confirm or cancel upcoming appointment | `GET /Appointment/{id}` + `PATCH /Appointment/{id}` |
| **patient_intake** | Outbound | Pre-visit intake (chief complaint, meds, allergies) | `GET /AllergyIntolerance` + `GET /MedicationStatement` + `POST /DocumentReference` |
| **post_discharge_followup** | Outbound | Recovery check, pain level, medication adherence | `POST /Observation` |
| **prescription_refill** | Outbound | Confirm refill, collect pharmacy preference | `POST /MedicationRequest` |
| **lab_results_notification** | Outbound | Fetch labs, notify patient, log acknowledgment | `GET /DiagnosticReport` + `POST /Communication` |
| **appointment_scheduling** | Inbound | Patient calls to schedule an appointment end-to-end | `GET /Patient` + `GET /Slot` + `POST /Appointment` |
| **care_gap_outreach** | Outbound | Preventive care gap outreach, schedule intent | `POST /CommunicationRequest` |
| **surgery_preop_checkin** | Outbound | Pre-op checklist (NPO, prep, transport, meds held) | `POST /DocumentReference` |
| **chronic_disease_monitoring** | Outbound | Collect BP, glucose, weight, symptoms | `GET /Condition` + `POST /Observation` (bundle) |
| **insurance_update** | Outbound | Collect and verify insurance before visit | `POST /Coverage` |

## Usage

Set environment variables first:

```bash
export GUAVA_AGENT_NUMBER="+1..."
export EPIC_BASE_URL="https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4"
export EPIC_ACCESS_TOKEN="..."
```

Outbound examples:

```bash
python -m examples.integrations.epic.appointment_confirmation "+15551234567" --name "Jane Doe" --appointment-id "abc123"

python -m examples.integrations.epic.patient_intake "+15551234567" --name "Jane Doe" --patient-id "pat456" --appointment "Friday at 2:00 PM"

python -m examples.integrations.epic.post_discharge_followup "+15551234567" --name "Jane Doe" --patient-id "pat456"

python -m examples.integrations.epic.prescription_refill "+15551234567" --name "Jane Doe" --patient-id "pat456" --medication "Metformin 500mg"

python -m examples.integrations.epic.lab_results_notification "+15551234567" --name "Jane Doe" --patient-id "pat456" --report-id "rpt789"

python -m examples.integrations.epic.care_gap_outreach "+15551234567" --name "Jane Doe" --patient-id "pat456" --care-gap "annual wellness visit"

python -m examples.integrations.epic.surgery_preop_checkin "+15551234567" --name "Jane Doe" --patient-id "pat456" --surgery-date "March 20th at 7:00 AM"

python -m examples.integrations.epic.chronic_disease_monitoring "+15551234567" --name "Jane Doe" --patient-id "pat456"

python -m examples.integrations.epic.insurance_update "+15551234567" --name "Jane Doe" --patient-id "pat456"
```

Inbound example (appointment_scheduling):

```bash
python -m examples.integrations.epic.appointment_scheduling
```

Use `--help` on any outbound example to see all arguments without placing a real call:

```bash
GUAVA_AGENT_NUMBER="+1..." EPIC_BASE_URL="https://..." EPIC_ACCESS_TOKEN="..." \
  python -m examples.integrations.epic.appointment_confirmation --help
```

## Environment Variables

All examples require `GUAVA_AGENT_NUMBER` plus the following Epic credentials:

| Variable | Description |
|---|---|
| `EPIC_BASE_URL` | Epic FHIR R4 base URL (e.g. `https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4`) |
| `EPIC_ACCESS_TOKEN` | OAuth 2.0 Bearer token obtained via Epic's backend system authorization flow |

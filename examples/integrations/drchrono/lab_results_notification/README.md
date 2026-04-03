# Lab Results Notification

**Direction:** Outbound

Proactively notifies a patient that their lab results are available at Oakridge Family Medicine. The agent confirms the notification was received, asks about scheduling a follow-up appointment, and records the patient's preferred contact method. The lab document status is updated to `patient_notified` in DrChrono.

## What it does

1. Fetches lab document metadata (description, lab name, date) via `GET /lab_documents/{lab_doc_id}`
2. Calls the patient and notifies them that results are available — without sharing any actual values
3. Collects acknowledgement, appointment preference, and preferred contact method
4. Updates the lab document status to `patient_notified` via `PATCH /lab_documents/{lab_doc_id}`
5. Logs the call via `POST /call_logs`

## HIPAA Note

This agent never reads out lab values or clinical findings over the phone. Only the existence and general description of the lab document (e.g., "your blood panel results") is mentioned. Identity is confirmed via the `reach_person` step before any health-related information is discussed. Do not share PHI in voicemails beyond the caller's name and the practice name.

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

python -m examples.integrations.drchrono.lab_results_notification "+15551234567" --lab-doc-id "7890" --patient-id "42" --name "Jane Doe"
```

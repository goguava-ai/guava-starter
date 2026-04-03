# Lab Results Notification — Epic Integration

An outbound voice agent that notifies patients when their lab results are ready. It fetches the `DiagnosticReport` from Epic before the call to personalize the message, then logs the patient's acknowledgment and callback preference as a `Communication` resource after the call.

## How It Works

**1. Before the call — fetch the diagnostic report from Epic**

The controller GETs `/DiagnosticReport/{report_id}` to retrieve the report's `code.text` (e.g. "Complete Blood Count"). This is used to tell the patient specifically which results are available ("your Complete Blood Count results are now available") rather than a generic message. Falls back gracefully if the fetch fails.

**2. Reach the patient**

`reach_person()` confirms a live person answered before delivering the notification. If unreachable, a voicemail is left letting the patient know their results are in the portal.

**3. Notify and collect acknowledgment**

The agent delivers the notification and collects:
- `acknowledged` — confirms the patient heard the message
- `has_questions` — whether they want to discuss the results with their provider
- `callback_requested` — whether they'd like a provider to call them back (only asked if they have questions)

**4. After the call — log a Communication in Epic**

`save_results()` posts a `Communication` resource (status `completed`) to Epic with a payload summarizing the notification outcome: whether the patient acknowledged, whether they had questions, and whether a callback was requested. This creates an auditable communication log in the patient's record.

**5. Outcome-based close**

- Callback requested → agent tells the patient their care team will call them back.
- No callback → agent directs the patient to the patient portal to view full results.

## Epic FHIR Calls

| Timing | Method | Resource | Purpose |
|---|---|---|---|
| Pre-call | `GET` | `DiagnosticReport/{id}` | Fetch report type to personalize the notification message |
| Post-call | `POST` | `Communication` | Log patient acknowledgment and callback preference |

## Setup

```bash
export GUAVA_AGENT_NUMBER="+1..."
export EPIC_BASE_URL="https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4"
export EPIC_ACCESS_TOKEN="..."
```

## Run

```bash
python -m examples.integrations.epic.lab_results_notification \
  "+15551234567" \
  --name "Jane Doe" \
  --patient-id "pat456" \
  --report-id "rpt789"
```

## Sample Output

```json
{
  "use_case": "lab_results_notification",
  "patient_name": "Jane Doe",
  "report_id": "rpt789",
  "fields": {
    "acknowledged": "yes",
    "has_questions": "yes",
    "callback_requested": "yes"
  }
}
```

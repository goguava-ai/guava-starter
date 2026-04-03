# Lab Results Notification

**Direction:** Outbound

The Sam agent places an outbound call to notify a patient that their lab results are available. If the patient answers, Sam fetches the most recent DiagnosticReport resources from Practice Fusion, summarizes their status in plain language, and asks whether the patient has any questions. If the patient has questions, the call ends with an assurance that a nurse will follow up. If the call goes unanswered, Sam leaves a brief voicemail that does not disclose any clinical details.

## What it does

1. Dials the patient and attempts to confirm the patient is on the line using `reach_person`.
2. On success, fetches `GET /DiagnosticReport?patient=Patient/<id>&_sort=-date&_count=5` to retrieve recent lab reports.
3. Summarizes report statuses in plain language for the agent to reference during the conversation.
4. Informs the patient their results are available and conveys the general status.
5. Asks whether the patient has questions about their results.
6. If yes: advises that a nurse will call back within one business day.
7. If no: reminds the patient to schedule any recommended follow-up visits.
8. On failure (no answer / voicemail): leaves a brief callback message with no clinical details.

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number (E.164 format) |
| `PRACTICE_FUSION_FHIR_BASE_URL` | Practice Fusion FHIR R4 base URL (e.g. `https://api.practicefusion.com/fhir/r4`) |
| `PRACTICE_FUSION_ACCESS_TOKEN` | OAuth 2.0 bearer token for Practice Fusion API access |

## Usage

```bash
python __main__.py +15551234567 \
  --name "Jane Smith" \
  --patient-id "abc123" \
  --result-summary "CBC and metabolic panel complete, all values within normal range"
```

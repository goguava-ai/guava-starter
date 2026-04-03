# Lab Results Callback

**Direction:** Outbound

Calls patients when their lab results are ready. The Riley agent fetches the DiagnosticReport from Practice Fusion, summarizes results at a high level (normal or abnormal), fields patient questions, and logs acknowledgment via a Communication resource.

## What it does

1. Fetches `GET /DiagnosticReport/<id>` before the call to determine the test name and overall result status (normal vs. abnormal) from the `conclusion` or `conclusionCode` fields.
2. Dials the patient and confirms they are on the line using `reach_person`.
3. Notifies the patient that their results are available and conveys the high-level status in plain language.
4. Asks whether the patient acknowledges the notification.
5. Asks whether the patient has questions for their provider; if yes, collects their question details.
6. Posts a `Communication` resource to Practice Fusion recording the outreach outcome: acknowledgment status and whether questions were logged.
7. Closes the call with appropriate next steps — callback from provider (if questions) or a reminder to check the patient portal.
8. If the call goes unanswered, leaves a brief voicemail with no clinical details.

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number (E.164 format) |
| `PRACTICE_FUSION_FHIR_BASE_URL` | Practice Fusion FHIR R4 base URL (e.g. `https://api.practicefusion.com/fhir/r4`) |
| `PRACTICE_FUSION_ACCESS_TOKEN` | OAuth 2.0 bearer token for Practice Fusion API access |

## Usage

```bash
python __main__.py +15551234567 \
  --name "Jane Doe" \
  --patient-id "patient-abc123" \
  --report-id "report-xyz789"
```

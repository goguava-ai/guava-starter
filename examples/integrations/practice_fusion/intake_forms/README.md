# Intake Forms

**Direction:** Outbound

Calls patients ahead of their visit to collect pre-visit intake information — chief complaint, symptom duration, pain scale rating, current medications, and allergies — then saves the responses as a DocumentReference in Practice Fusion for the care team to review.

## What it does

1. Dials the patient and confirms they are on the line using `reach_person`.
2. Introduces the call as a quick pre-visit intake on behalf of Sunrise Family Practice.
3. Collects the following fields:
   - Chief complaint (main reason for the visit)
   - Symptom duration (how long they have had the issue)
   - Pain/discomfort level on a 1–10 scale (grouped into brackets)
   - Current medications (prescriptions, OTC drugs, supplements)
   - Known allergies
   - Any additional concerns for the provider (optional)
4. Assembles a plain-text intake note from the collected fields.
5. POSTs a `DocumentReference` (LOINC 34117-2 — History and Physical Note) to Practice Fusion with the intake note as a base64-encoded attachment.
6. Closes the call by thanking the patient and reminding them to arrive 10 minutes early.
7. If the call goes unanswered, leaves a brief voicemail asking the patient to call back.

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
  --appointment-date "Friday at 2:00 PM"
```

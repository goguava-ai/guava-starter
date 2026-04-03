# Appointment Reminder

**Direction:** Outbound

Calls patients the day before their appointment to confirm attendance or record a cancellation, then patches the appointment status in Practice Fusion.

## What it does

1. Dials the patient and confirms they are on the line using `reach_person`.
2. Fetches `GET /Appointment/<id>` to retrieve the appointment's start time, service type, and attending provider.
3. Reminds the patient of the appointment date, time, and provider.
4. Asks whether they plan to attend or need to cancel.
5. If cancelling, collects a brief reason from the patient.
6. Patches `PATCH /Appointment/<id>` to set `status: "booked"` or `status: "cancelled"`. If a cancellation reason was given, it is stored in the `comment` field.
7. Closes the call with a confirmation message or a note that the scheduling team will follow up.
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
  --appointment-id "appt-xyz789"
```

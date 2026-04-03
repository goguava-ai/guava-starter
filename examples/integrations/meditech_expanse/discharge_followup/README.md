# Discharge Follow-up

**Direction:** Outbound

An outbound voice agent that calls recently discharged patients 24–48 hours after leaving St. Raphael Medical Center to conduct a wellness check, collecting pain level, medication adherence, and symptom data, then posting all results as a FHIR Observation bundle and escalating to the care team when clinically warranted.

## What it does

1. Places an outbound call and attempts to reach the patient by name using `reach_person`.
2. If connected: fetches the patient's most recent finished `Encounter` from Meditech Expanse to personalize the greeting with their discharge reason.
3. Collects a 0–10 numeric pain level rating.
4. Asks whether the patient has been taking their prescribed discharge medications as directed.
5. Asks whether the patient has experienced any concerning symptoms (fever, shortness of breath, chest pain, etc.) and collects a brief description if yes.
6. Asks whether a follow-up appointment is already scheduled.
7. POSTs all collected data to Meditech Expanse as a FHIR `Bundle` (transaction) containing four individual `Observation` resources — one per data point.
8. If pain score is 7 or higher, or the patient reports concerning symptoms: creates a FHIR `Flag` resource in Meditech to alert the care team, then advises the patient to seek immediate care.
9. Otherwise closes with contextual guidance (medication reminders, scheduling assistance).
10. If the patient does not answer: leaves a brief voicemail asking them to call back.

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Phone number the outbound call is placed from (E.164 format) |
| `MEDITECH_FHIR_BASE_URL` | Meditech Expanse FHIR R4 base URL (e.g. `https://fhir.meditech.com/r4`) |
| `MEDITECH_ACCESS_TOKEN` | OAuth 2.0 bearer token for the Meditech Expanse FHIR API |

## Usage

```bash
export GUAVA_AGENT_NUMBER="+1..."
export MEDITECH_FHIR_BASE_URL="https://fhir.meditech.com/r4"
export MEDITECH_ACCESS_TOKEN="..."

python __main__.py +15551234567 --name "Jane Smith" --patient-id PT-00123 --discharge-date 2026-03-28
```

Use `--help` to see all arguments without placing a call:

```bash
python __main__.py --help
```

## Meditech FHIR Calls

| Timing | Method | Resource | Purpose |
|---|---|---|---|
| On connect | `GET` | `Encounter` | Fetch most recent finished encounter for discharge context |
| Post-collection | `POST` | `Bundle` (transaction) | Post pain, adherence, symptoms, and follow-up as Observation bundle |
| If escalating | `POST` | `Flag` | Alert care team to high pain score or concerning symptoms |

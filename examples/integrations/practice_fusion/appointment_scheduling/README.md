# Appointment Scheduling

**Direction:** Inbound

When a patient calls Riverside Family Medicine to book an appointment, the Jordan agent collects their name, date of birth, appointment type, and scheduling preferences. It then looks up the patient record in Practice Fusion via the FHIR R4 API, searches for available slots on or after their preferred date, presents the first matching slot, and books the appointment by POSTing a FHIR Appointment resource. The patient receives a confirmation number before the call ends.

## What it does

1. Greets the patient and collects first name, last name, and date of birth.
2. Collects appointment type (e.g., annual physical, sick visit) and preferred date.
3. Asks whether the patient prefers a morning or afternoon slot.
4. Searches `GET /Patient?family=<last>&birthdate=<dob>` to look up the patient record.
5. Searches `GET /Slot?start=ge<date>&status=free` to find available appointment slots.
6. Filters results by the patient's morning/afternoon preference and presents the first match.
7. Books the appointment via `POST /Appointment` with a FHIR Appointment resource.
8. Reads back the confirmation number and thanks the patient.

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number (E.164 format) |
| `PRACTICE_FUSION_FHIR_BASE_URL` | Practice Fusion FHIR R4 base URL (e.g. `https://api.practicefusion.com/fhir/r4`) |
| `PRACTICE_FUSION_ACCESS_TOKEN` | OAuth 2.0 bearer token for Practice Fusion API access |

## Usage

```bash
python __main__.py
```

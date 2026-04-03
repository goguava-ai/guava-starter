# Patient Lookup

**Direction:** Inbound

Verifies a patient's identity and retrieves their FHIR Patient record from Cerner. If the caller is asking about appointments, upcoming Appointments are fetched and summarized.

## What it does

1. Collects last name, first name, date of birth, and optionally MRN
2. Searches for the patient via `GET /Patient?identifier={mrn}` or `GET /Patient?family=...&given=...&birthdate=...`
3. Optionally fetches upcoming Appointments via `GET /Appointment?patient={id}&date=ge{today}`
4. Delivers a personalized response based on their reason for calling

## FHIR Resources Used

| Resource | Operation |
|---|---|
| `Patient` | Search by MRN or name + DOB |
| `Appointment` | List upcoming appointments |

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `CERNER_FHIR_BASE_URL` | Cerner FHIR R4 base URL |
| `CERNER_ACCESS_TOKEN` | OAuth 2.0 Bearer token |

## Usage

```bash
python __main__.py
```

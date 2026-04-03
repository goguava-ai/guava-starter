# Appointment Scheduling

**Direction:** Inbound

A patient calls to schedule an appointment. The agent verifies their identity, captures the appointment type and preferred time, and creates a FHIR `Appointment` resource in Cerner.

## What it does

1. Looks up the patient by MRN via `GET /Patient?identifier={mrn}`
2. Collects appointment type, reason for visit, preferred slot, and insurance status
3. Creates a FHIR `Appointment` resource via `POST /Appointment` with a 30-minute duration
4. Routes to the appropriate `Practitioner` based on appointment type (configured via env vars)

## FHIR Resources Used

| Resource | Operation |
|---|---|
| `Patient` | Search by MRN |
| `Appointment` | Create |

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `CERNER_FHIR_BASE_URL` | Cerner FHIR R4 base URL |
| `CERNER_ACCESS_TOKEN` | OAuth 2.0 Bearer token |
| `CERNER_PRACTITIONER_PCP` | Practitioner ID for primary care |
| `CERNER_PRACTITIONER_SPECIALIST` | Practitioner ID for specialist |
| `CERNER_PRACTITIONER_URGENT` | Practitioner ID for urgent care |
| `CERNER_PRACTITIONER_LAB` | Practitioner ID for lab |
| `CERNER_PRACTITIONER_IMAGING` | Practitioner ID for imaging |

## Usage

```bash
python __main__.py
```

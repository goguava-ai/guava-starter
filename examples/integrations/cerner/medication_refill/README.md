# Medication Refill

**Direction:** Inbound

A patient calls to request a prescription refill. The agent verifies their identity, identifies the medication and preferred pharmacy, flags any side effect concerns for the provider, and submits a FHIR `ServiceRequest`.

## What it does

1. Verifies the patient by MRN via `GET /Patient?identifier={mrn}`
2. Optionally lists active `MedicationRequest` resources via `GET /MedicationRequest?patient={id}&status=active`
3. Collects medication name, preferred pharmacy, urgency, and any side effect concerns
4. Creates a `ServiceRequest` via `POST /ServiceRequest` with pharmacy routing details
5. If side effects are reported, flags the request for provider review before dispensing

## FHIR Resources Used

| Resource | Operation |
|---|---|
| `Patient` | Search by MRN |
| `MedicationRequest` | List active medications |
| `ServiceRequest` | Create refill request |

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

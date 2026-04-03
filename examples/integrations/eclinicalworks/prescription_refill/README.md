# Prescription Refill

**Direction:** Outbound

Calls a patient to confirm a refill request, check for new symptoms, and collect pharmacy preference. Posts a FHIR MedicationRequest to the eClinicalWorks chart on completion.

## What it does

1. Calls the patient to confirm they still need the refill
2. Checks for new symptoms that the care team should review
3. Collects preferred pharmacy
4. Posts a `MedicationRequest` via `POST /MedicationRequest`

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `ECW_BASE_URL` | eClinicalWorks FHIR R4 base URL |
| `ECW_TOKEN_URL` | OAuth token endpoint |
| `ECW_CLIENT_ID` | SMART on FHIR client ID |
| `ECW_CLIENT_SECRET` | SMART on FHIR client secret |

## Usage

```bash
python -m examples.integrations.eclinicalworks.prescription_refill "+15551234567" --name "Jane Doe" --patient-id "pat-456" --medication "Metformin 500mg"
```

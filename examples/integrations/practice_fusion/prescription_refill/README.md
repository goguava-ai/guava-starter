# Prescription Refill

**Direction:** Inbound

When a patient calls Riverside Family Medicine to request a prescription refill, the Alex agent collects their identity, verifies them against the Practice Fusion FHIR record, and confirms the requested medication is among their active prescriptions. It then submits a refill request as a new FHIR MedicationRequest with `intent=plan`, notes the patient's pharmacy preference, and lets the patient know the request is pending provider approval.

## What it does

1. Greets the patient and collects first name, last name, and date of birth.
2. Collects the name of the medication to be refilled.
3. Asks whether the patient prefers their pharmacy on file, a different pharmacy, or mail order.
4. Searches `GET /Patient?family=<last>&birthdate=<dob>` to verify the patient record.
5. Fetches `GET /MedicationRequest?patient=Patient/<id>&status=active` to retrieve active prescriptions.
6. Matches the requested medication name against the active prescription list.
7. POSTs a new `MedicationRequest` with `intent=plan` and a note recording the pharmacy preference.
8. Confirms the request number and expected approval timeline with the patient.

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

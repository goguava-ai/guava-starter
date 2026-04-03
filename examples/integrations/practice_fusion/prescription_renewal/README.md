# Prescription Renewal

**Direction:** Inbound

A patient calls to request a prescription renewal. The Morgan agent verifies their identity, looks up their active medications in Practice Fusion, confirms which medication they need renewed, and posts a new MedicationRequest for provider review.

## What it does

1. Greets the patient and collects first name, last name, and date of birth.
2. Asks which medication they need renewed and their preferred pharmacy.
3. Optionally collects any notes the patient wants to pass along to the provider.
4. Searches `GET /Patient?family=<last>&birthdate=<dob>` to verify the patient record.
5. Fetches `GET /MedicationRequest?patient=Patient/<id>&status=active` to retrieve active prescriptions.
6. Matches the requested medication name against the active prescription list (case-insensitive substring match).
7. If no match is found, advises the patient to call back during office hours.
8. POSTs a new `MedicationRequest` with `intent: "proposal"` and a note recording the pharmacy preference and any patient comments.
9. Confirms the renewal is pending provider review and gives the patient an expected timeline.

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

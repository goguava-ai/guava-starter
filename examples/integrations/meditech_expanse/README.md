# Meditech Expanse Integration

Voice agents that integrate with [Meditech Expanse](https://www.meditech.com/solutions/expanse) to handle patient communications across hospital workflows.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`appointment_confirmation`](appointment_confirmation/) | Outbound | Calls patients ahead of scheduled appointments to confirm attendance or capture cancellations with a reason, then updates the FHIR Appointment status in Meditech |
| [`discharge_followup`](discharge_followup/) | Outbound | Post-discharge wellness check that collects pain level, medication adherence, and symptom data; posts results as a FHIR Observation bundle and creates a Flag to escalate to the care team if symptoms are concerning |
| [`patient_registration`](patient_registration/) | Inbound | Patient calls to provide or update demographic and insurance information before a visit; agent collects all fields and writes a complete Patient resource to Meditech via PUT (existing) or POST (new) |
| [`medication_reconciliation`](medication_reconciliation/) | Outbound | Pre-admission call that fetches the patient's active MedicationRequests from Meditech, confirms which medications they are still taking, captures any unlisted medications or new allergies, and saves a reconciliation note as a FHIR DocumentReference |

## Authentication

Meditech Expanse uses OAuth 2.0 bearer token authentication on its FHIR R4 API. Obtain an access token via Meditech's backend authorization flow and set it as `MEDITECH_ACCESS_TOKEN`. Tokens should be rotated before expiry; for production use, implement a token refresh wrapper around `get_headers()`.

All requests include `Accept: application/fhir+json` in addition to the `Authorization: Bearer <token>` and `Content-Type: application/json` headers.

## Common Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number (E.164 format, e.g. `+15551234567`) |
| `MEDITECH_FHIR_BASE_URL` | Meditech Expanse FHIR R4 base URL (e.g. `https://fhir.meditech.com/r4`) |
| `MEDITECH_ACCESS_TOKEN` | OAuth 2.0 Bearer token for the Meditech Expanse FHIR API |

## Usage

Set environment variables, then run inbound or outbound examples:

```bash
export GUAVA_AGENT_NUMBER="+1..."
export MEDITECH_FHIR_BASE_URL="https://fhir.meditech.com/r4"
export MEDITECH_ACCESS_TOKEN="..."
```

Inbound (patient_registration):

```bash
python __main__.py
```

Outbound examples:

```bash
# Appointment confirmation
python __main__.py +15551234567 --name "Maria Gonzalez" --patient-id PT-00456 --appointment-id APT-00789

# Discharge follow-up
python __main__.py +15551234567 --name "Jane Smith" --patient-id PT-00123 --discharge-date 2026-03-28

# Medication reconciliation
python __main__.py +15551234567 --name "Robert Chen" --patient-id PT-00789
```

Run any outbound script with `--help` to see all arguments without placing a call.

## FHIR API Reference

| Resource | Endpoint | Used By |
|---|---|---|
| `Appointment` (read) | `GET {base}/Appointment/{id}` | appointment_confirmation |
| `Appointment` (update) | `PATCH {base}/Appointment/{id}` | appointment_confirmation |
| `Encounter` (search) | `GET {base}/Encounter?patient=Patient/{id}&status=finished&_sort=-date&_count=1` | discharge_followup |
| `Bundle` (transaction) | `POST {base}` | discharge_followup |
| `Flag` (create) | `POST {base}/Flag` | discharge_followup |
| `Patient` (search) | `GET {base}/Patient?family=<last>&birthdate=<dob>` | patient_registration |
| `Patient` (create) | `POST {base}/Patient` | patient_registration |
| `Patient` (full update) | `PUT {base}/Patient/{id}` | patient_registration |
| `MedicationRequest` (search) | `GET {base}/MedicationRequest?subject=Patient/{id}&status=active` | medication_reconciliation |
| `DocumentReference` (create) | `POST {base}/DocumentReference` | medication_reconciliation |

Official Meditech Expanse FHIR R4 documentation: https://home.meditech.com/en/d/restapiresources/pages/apidoc.htm

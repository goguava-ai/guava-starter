# Cerner / Oracle Health Integration

Voice agents that integrate with the [Cerner FHIR R4 API](https://fhir.cerner.com/millennium/r4/) to look up patients, schedule appointments, notify patients of lab results, and process medication refill requests — enabling compliant, EHR-connected voice workflows for health systems.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`patient_lookup`](patient_lookup/) | Inbound | Verify patient identity and retrieve their record and upcoming appointments from Cerner |
| [`appointment_scheduling`](appointment_scheduling/) | Inbound | Patient calls to book an appointment; creates a FHIR `Appointment` resource |
| [`lab_results_notification`](lab_results_notification/) | Outbound | Call patient to notify them that lab results are ready; logs a FHIR `Communication` resource |
| [`medication_refill`](medication_refill/) | Inbound | Patient requests a prescription refill; creates a FHIR `ServiceRequest` for the provider |

## Authentication

All examples use OAuth 2.0 Bearer token authentication against the FHIR R4 endpoint:

```python
FHIR_HEADERS = {
    "Authorization": f"Bearer {CERNER_ACCESS_TOKEN}",
    "Accept": "application/fhir+json",
}
```

Obtain tokens via the [Cerner SMART on FHIR / OAuth 2.0 flow](https://fhir.cerner.com/authorization/). For backend integrations, use the **Client Credentials** or **System Account** grant type.

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `CERNER_FHIR_BASE_URL` | FHIR R4 base URL (e.g. `https://fhir-ehr-code.cerner.com/r4/{tenant-id}`) |
| `CERNER_ACCESS_TOKEN` | OAuth 2.0 Bearer token |
| `CERNER_PRACTITIONER_PCP` | *(appointment_scheduling)* FHIR Practitioner ID for primary care |
| `CERNER_PRACTITIONER_SPECIALIST` | *(appointment_scheduling)* FHIR Practitioner ID for specialist |
| `CERNER_PRACTITIONER_URGENT` | *(appointment_scheduling)* FHIR Practitioner ID for urgent care |
| `CERNER_PRACTITIONER_LAB` | *(appointment_scheduling)* FHIR Practitioner ID for lab |
| `CERNER_PRACTITIONER_IMAGING` | *(appointment_scheduling)* FHIR Practitioner ID for imaging |

## FHIR Resources Used

| Resource | Used In |
|---|---|
| `Patient` | patient_lookup, appointment_scheduling, medication_refill |
| `Appointment` | appointment_scheduling |
| `Observation` | lab_results_notification |
| `Communication` | lab_results_notification |
| `MedicationRequest` | medication_refill |
| `ServiceRequest` | medication_refill |

## HIPAA Note

These examples handle Protected Health Information (PHI). Ensure your deployment complies with HIPAA requirements: encrypt data in transit (TLS), restrict access via IAM, log all PHI access, and execute a Business Associate Agreement (BAA) with all service providers.

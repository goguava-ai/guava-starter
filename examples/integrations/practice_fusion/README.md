# Practice Fusion Integration

Voice agents that integrate with the [Practice Fusion EHR API](https://www.practicefusion.com/developer-center/) to handle appointment reminders, prescription renewals, lab result callbacks, and pre-visit intake — across both inbound and outbound call patterns.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`appointment_reminder`](appointment_reminder/) | Outbound | Calls patients the day before their appointment to confirm or cancel; patches the appointment status in Practice Fusion |
| [`prescription_renewal`](prescription_renewal/) | Inbound | Patient calls to request a prescription renewal; agent verifies identity, looks up active medications, and posts a MedicationRequest for provider review |
| [`lab_results_callback`](lab_results_callback/) | Outbound | Calls patients when lab results are ready; fetches the DiagnosticReport, delivers a high-level normal/abnormal summary, and logs acknowledgment via a Communication resource |
| [`intake_forms`](intake_forms/) | Outbound | Pre-visit intake call; collects chief complaint, symptom duration, pain scale, medications, and allergies, then saves responses as a DocumentReference |
| [`appointment_scheduling`](appointment_scheduling/) | Inbound | Patient calls to book an appointment; agent collects preferences, finds an available Slot, and books it via FHIR |

## Authentication

Practice Fusion uses **OAuth 2.0 Bearer tokens** for all FHIR R4 API requests. Obtain an access token through your Practice Fusion developer account and pass it in the `Authorization` header:

```python
headers = {"Authorization": f"Bearer {os.environ['PRACTICE_FUSION_ACCESS_TOKEN']}"}
```

Tokens are scoped to specific FHIR resource types. Ensure the token used for each example has read/write access to the resources it touches (see the FHIR Resources table below).

## Common Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number (E.164 format, e.g. `+15550001234`) |
| `PRACTICE_FUSION_FHIR_BASE_URL` | Practice Fusion FHIR R4 base URL (e.g. `https://api.practicefusion.com/fhir/r4`) |
| `PRACTICE_FUSION_ACCESS_TOKEN` | OAuth 2.0 bearer token for authenticating all FHIR API requests |

## FHIR Resources Used

| Resource | Used By |
|---|---|
| [`Appointment`](https://www.hl7.org/fhir/R4/appointment.html) | `appointment_reminder`, `appointment_scheduling` |
| [`Patient`](https://www.hl7.org/fhir/R4/patient.html) | `prescription_renewal`, `appointment_scheduling` |
| [`MedicationRequest`](https://www.hl7.org/fhir/R4/medicationrequest.html) | `prescription_renewal` |
| [`DiagnosticReport`](https://www.hl7.org/fhir/R4/diagnosticreport.html) | `lab_results_callback` |
| [`Communication`](https://www.hl7.org/fhir/R4/communication.html) | `lab_results_callback` |
| [`DocumentReference`](https://www.hl7.org/fhir/R4/documentreference.html) | `intake_forms` |
| [`Slot`](https://www.hl7.org/fhir/R4/slot.html) | `appointment_scheduling` |

## Practice Fusion API Reference

- [FHIR Developer Guide](https://www.practicefusion.com/fhir/)
- [HL7 FHIR R4 Specification](https://www.hl7.org/fhir/R4/)

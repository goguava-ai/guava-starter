# NextGen Healthcare Integration

Voice agents that integrate with the [NextGen Healthcare FHIR R4 API](https://fhir.nextgen.com) to confirm appointments, conduct pre-visit intake, support specialist referral follow-up, and schedule new appointments — using the same US Core FHIR profile patterns as the Epic and eClinicalWorks integrations.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`appointment_confirmation`](appointment_confirmation/) | Outbound | Confirm or cancel an upcoming appointment; PATCH status in NextGen |
| [`patient_intake`](patient_intake/) | Outbound | Pre-visit intake — chief complaint, medications, allergies |
| [`referral_followup`](referral_followup/) | Outbound | Follow up on a specialist referral; confirm receipt and scheduling intent |
| [`appointment_scheduling`](appointment_scheduling/) | Inbound | Patient calls to schedule; search Slots and POST Appointment |

## Authentication

All examples use OAuth 2.0 SMART on FHIR Bearer tokens:

```python
resp = requests.post(
    os.environ["NEXTGEN_TOKEN_URL"],
    data={"grant_type": "client_credentials", "scope": "system/*.read system/*.write"},
    auth=(os.environ["NEXTGEN_CLIENT_ID"], os.environ["NEXTGEN_CLIENT_SECRET"]),
)
access_token = resp.json()["access_token"]
headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json",
}
```

## Base URL

```
https://fhir.nextgen.com/nge/prod/fhir-api-r4/fhir/R4
```

## Common Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `NEXTGEN_BASE_URL` | NextGen FHIR R4 base URL |
| `NEXTGEN_TOKEN_URL` | OAuth token endpoint |
| `NEXTGEN_CLIENT_ID` | SMART on FHIR client ID |
| `NEXTGEN_CLIENT_SECRET` | SMART on FHIR client secret |

## Usage

```bash
export GUAVA_AGENT_NUMBER="+1..."
export NEXTGEN_BASE_URL="https://fhir.nextgen.com/nge/prod/fhir-api-r4/fhir/R4"
export NEXTGEN_TOKEN_URL="https://fhir.nextgen.com/nge/prod/nge-oauth/token"
export NEXTGEN_CLIENT_ID="..."
export NEXTGEN_CLIENT_SECRET="..."
```

Outbound examples:

```bash
python -m examples.integrations.nextgen_healthcare.appointment_confirmation "+15551234567" --name "Jane Doe" --appointment-id "apt-123"
python -m examples.integrations.nextgen_healthcare.patient_intake "+15551234567" --name "Jane Doe" --patient-id "pat-456" --appointment "Thursday at 3:30 PM"
python -m examples.integrations.nextgen_healthcare.referral_followup "+15551234567" --name "Jane Doe" --patient-id "pat-456" --referral-specialty "Cardiology"
```

Inbound example:

```bash
python -m examples.integrations.nextgen_healthcare.appointment_scheduling
```

## NextGen Healthcare FHIR API Reference

- [Patient](https://fhir.nextgen.com/nge/prod/fhir-api-r4/fhir/R4/Patient)
- [Appointment](https://fhir.nextgen.com/nge/prod/fhir-api-r4/fhir/R4/Appointment)
- [Slot](https://fhir.nextgen.com/nge/prod/fhir-api-r4/fhir/R4/Slot)
- [MedicationRequest](https://fhir.nextgen.com/nge/prod/fhir-api-r4/fhir/R4/MedicationRequest)
- [ServiceRequest](https://fhir.nextgen.com/nge/prod/fhir-api-r4/fhir/R4/ServiceRequest)

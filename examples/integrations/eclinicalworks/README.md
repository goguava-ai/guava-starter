# eClinicalWorks Integration

Voice agents that integrate with the [eClinicalWorks FHIR R4 API](https://developer.eclinicalworks.com) to manage appointments, conduct patient intake, request prescription refills, and perform care gap outreach — matching the clinical workflow patterns used in Epic and NextGen integrations.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`appointment_confirmation`](appointment_confirmation/) | Outbound | Confirm or cancel an upcoming appointment |
| [`patient_intake`](patient_intake/) | Outbound | Pre-visit intake — chief complaint, current medications, allergies |
| [`prescription_refill`](prescription_refill/) | Outbound | Confirm refill, capture pharmacy preference, post MedicationRequest |
| [`care_gap_outreach`](care_gap_outreach/) | Outbound | Preventive care gap outreach; capture scheduling intent |

## Authentication

All examples use OAuth 2.0 Bearer tokens via the SMART on FHIR client credentials flow:

```python
resp = requests.post(
    os.environ["ECW_TOKEN_URL"],
    data={"grant_type": "client_credentials", "scope": "system/*.read system/*.write"},
    auth=(os.environ["ECW_CLIENT_ID"], os.environ["ECW_CLIENT_SECRET"]),
)
access_token = resp.json()["access_token"]
headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json",
}
```

## Base URL

```
https://fhir.eclinicalworks.com/fhir/r4
```

Set `ECW_BASE_URL` to your eClinicalWorks FHIR R4 endpoint. Sandbox and production URLs are provided by eClinicalWorks upon app registration.

## Common Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `ECW_BASE_URL` | eClinicalWorks FHIR R4 base URL |
| `ECW_TOKEN_URL` | OAuth token endpoint |
| `ECW_CLIENT_ID` | SMART on FHIR client ID |
| `ECW_CLIENT_SECRET` | SMART on FHIR client secret |

## Usage

```bash
export GUAVA_AGENT_NUMBER="+1..."
export ECW_BASE_URL="https://fhir.eclinicalworks.com/fhir/r4"
export ECW_TOKEN_URL="https://fhir.eclinicalworks.com/oauth2/token"
export ECW_CLIENT_ID="..."
export ECW_CLIENT_SECRET="..."
```

Outbound examples:

```bash
python -m examples.integrations.eclinicalworks.appointment_confirmation "+15551234567" --name "Jane Doe" --appointment-id "apt-abc123"
python -m examples.integrations.eclinicalworks.patient_intake "+15551234567" --name "Jane Doe" --patient-id "pat-456" --appointment "Monday at 10:00 AM"
python -m examples.integrations.eclinicalworks.prescription_refill "+15551234567" --name "Jane Doe" --patient-id "pat-456" --medication "Metformin 500mg"
python -m examples.integrations.eclinicalworks.care_gap_outreach "+15551234567" --name "Jane Doe" --patient-id "pat-456" --care-gap "annual wellness visit"
```

## eClinicalWorks FHIR API Reference

- [Appointment](https://fhir.eclinicalworks.com/fhir/r4/Appointment)
- [Patient](https://fhir.eclinicalworks.com/fhir/r4/Patient)
- [MedicationRequest](https://fhir.eclinicalworks.com/fhir/r4/MedicationRequest)
- [AllergyIntolerance](https://fhir.eclinicalworks.com/fhir/r4/AllergyIntolerance)
- [CommunicationRequest](https://fhir.eclinicalworks.com/fhir/r4/CommunicationRequest)

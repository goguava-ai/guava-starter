# Athenahealth Integration

Voice agents that integrate with the [Athenahealth REST API](https://docs.developer.athenahealth.com) to handle appointment scheduling, patient intake, prescription refills, and insurance verification — without routing patients to a portal or live agent.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`appointment_confirmation`](appointment_confirmation/) | Outbound | Confirm or cancel an upcoming appointment |
| [`appointment_scheduling`](appointment_scheduling/) | Inbound | Patient calls to schedule a new appointment end-to-end |
| [`patient_intake`](patient_intake/) | Outbound | Pre-visit intake — chief complaint, medications, allergies |
| [`prescription_refill`](prescription_refill/) | Outbound | Confirm refill request and preferred pharmacy |
| [`insurance_verification`](insurance_verification/) | Outbound | Collect and confirm insurance details before a visit |

## Authentication

All examples use OAuth 2.0 Bearer tokens obtained via the client credentials flow:

```python
resp = requests.post(
    "https://api.platform.athenahealth.com/oauth2/v1/token",
    data={"grant_type": "client_credentials"},
    auth=(ATHENA_CLIENT_ID, ATHENA_CLIENT_SECRET),
)
access_token = resp.json()["access_token"]
headers = {"Authorization": f"Bearer {access_token}"}
```

## Base URL

```
https://api.platform.athenahealth.com/v1/{practice_id}/
```

Set `ATHENA_PRACTICE_ID` to your practice identifier. Athenahealth uses a sandbox environment (`preview.platform.athenahealth.com`) for testing.

## Common Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `ATHENA_CLIENT_ID` | Athenahealth OAuth client ID |
| `ATHENA_CLIENT_SECRET` | Athenahealth OAuth client secret |
| `ATHENA_PRACTICE_ID` | Practice identifier |

## Usage

```bash
export GUAVA_AGENT_NUMBER="+1..."
export ATHENA_CLIENT_ID="..."
export ATHENA_CLIENT_SECRET="..."
export ATHENA_PRACTICE_ID="..."
```

Outbound examples:

```bash
python -m examples.integrations.athenahealth.appointment_confirmation "+15551234567" --name "Jane Doe" --appointment-id "12345"
python -m examples.integrations.athenahealth.patient_intake "+15551234567" --name "Jane Doe" --patient-id "67890" --appointment "Friday at 2:00 PM"
python -m examples.integrations.athenahealth.prescription_refill "+15551234567" --name "Jane Doe" --patient-id "67890" --medication "Lisinopril 10mg"
python -m examples.integrations.athenahealth.insurance_verification "+15551234567" --name "Jane Doe" --patient-id "67890"
```

Inbound example:

```bash
python -m examples.integrations.athenahealth.appointment_scheduling
```

## Athenahealth API Reference

- [Appointments](https://docs.developer.athenahealth.com/docs/appointments)
- [Patients](https://docs.developer.athenahealth.com/docs/patients)
- [Medications](https://docs.developer.athenahealth.com/docs/medications)
- [Insurance](https://docs.developer.athenahealth.com/docs/insurance)

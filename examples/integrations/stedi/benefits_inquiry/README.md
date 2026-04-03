# Benefits Inquiry

**Direction:** Inbound

A patient calls to find out what they'll owe for an upcoming service. The agent collects their insurance details and the type of service, submits a targeted eligibility check (X12 270/271) to Stedi using the appropriate service type codes, and reads back their copay, deductible, and out-of-pocket maximum.

## What it does

1. Collects insurance info and the service type (primary care, specialist, hospital, urgent care, mental health, or pharmacy)
2. Maps the service type to X12 service type codes (e.g., `UC` for urgent care, `MH` for mental health, `88` for pharmacy)
3. Posts to `POST /change/medicalnetwork/eligibility/v3`
4. Parses `benefitsInformation[]` for copay (code `B`), deductible (code `C`), out-of-pocket max (code `G`), and coinsurance (code `A`)
5. Explains each benefit term in plain language and reads back the patient's cost-sharing amounts

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `STEDI_API_KEY` | Stedi API key |
| `STEDI_PROVIDER_NPI` | Provider NPI number |
| `STEDI_PROVIDER_NAME` | Provider organization name (optional) |

## Usage

```bash
python -m examples.integrations.stedi.benefits_inquiry
```

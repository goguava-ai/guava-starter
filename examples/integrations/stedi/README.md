# Stedi Integration

Voice agents that integrate with the [Stedi Healthcare API](https://www.stedi.com/docs) to handle real-time insurance eligibility, claims, remittance, and insurance discovery — enabling clinical and billing staff to resolve coverage questions without logging into a portal.

## Examples

| Example | Direction | Description | Stedi API |
|---|---|---|---|
| [`eligibility_check`](eligibility_check/) | Inbound | Patient calls to verify their insurance is active before a visit | `POST /change/medicalnetwork/eligibility/v3` |
| [`benefits_inquiry`](benefits_inquiry/) | Inbound | Patient asks about their copay, deductible, and out-of-pocket max for a specific service | `POST /change/medicalnetwork/eligibility/v3` |
| [`claim_status_check`](claim_status_check/) | Inbound | Patient calls billing to check on a submitted claim | `POST /change/medicalnetwork/claimstatus/v2` |
| [`era_payment_lookup`](era_payment_lookup/) | Inbound | Billing staff retrieves 835 ERA remittance details for a transaction | `GET /change/medicalnetwork/reports/v2/{id}/835` |
| [`insurance_discovery`](insurance_discovery/) | Outbound | Discover active insurance plans for a patient who has none on file | `POST /insurance-discovery/check/v1` |
| [`pre_appointment_eligibility`](pre_appointment_eligibility/) | Outbound | Call patient the day before to confirm their coverage is active; alert them to issues | `POST /change/medicalnetwork/eligibility/v3` |
| [`claim_denial_notification`](claim_denial_notification/) | Outbound | Notify patient of a claim denial and help them choose a next step (appeal, payment plan, billing review) | `POST /change/medicalnetwork/claimstatus/v2` |

## Authentication

All examples authenticate with a Stedi API key in the `Authorization` header:

```python
headers = {"Authorization": f"Key {STEDI_API_KEY}"}
```

Get your API key from the [Stedi portal](https://portal.stedi.com) under **Settings → API Keys**. Use a test key for development.

## Base URL

```
https://healthcare.us.stedi.com/2024-04-01
```

## Common Patterns

**Inbound eligibility and claims** — Collect subscriber identity from the caller, build the X12 270/276 JSON payload, POST to Stedi, and read back the parsed result. A random 9-digit `controlNumber` is generated per request to correlate Stedi's response.

**Outbound pre-call API** — For `pre_appointment_eligibility` and `claim_denial_notification`, the Stedi API call runs in `__init__` before the outbound call is placed. By the time the patient answers, results are already in memory.

**Async insurance discovery** — `insurance_discovery` submits a request and polls `GET /insurance-discovery/check/v1/{id}` up to 6 times (5-second intervals) before the call connects.

## Common Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `STEDI_API_KEY` | Stedi API key from the portal |
| `STEDI_PROVIDER_NPI` | Your organization's NPI number |
| `STEDI_PROVIDER_NAME` | Your organization name (optional, defaults to `Ridgeline Health`) |

## Usage

Inbound examples:

```bash
python -m examples.integrations.stedi.eligibility_check
python -m examples.integrations.stedi.benefits_inquiry
python -m examples.integrations.stedi.claim_status_check
python -m examples.integrations.stedi.era_payment_lookup
```

Outbound examples:

```bash
python -m examples.integrations.stedi.insurance_discovery \
  "+15551234567" --name "Jane Doe" --first-name Jane --last-name Doe --dob 1985-03-15

python -m examples.integrations.stedi.pre_appointment_eligibility \
  "+15551234567" --name "Jane Doe" --first-name Jane --last-name Doe --dob 1985-03-15 \
  --member-id XYZ123456 --payer-id BCBS --appointment-date "March 27th at 2:00 PM"

python -m examples.integrations.stedi.claim_denial_notification \
  "+15551234567" --name "Jane Doe" --first-name Jane --last-name Doe --dob 1985-03-15 \
  --member-id XYZ123456 --payer-id BCBS --claim-number 100001 \
  --service "your March 10th office visit"
```

## Stedi API Reference

- [Eligibility Checks (270/271)](https://www.stedi.com/docs/healthcare/eligibility)
- [Claim Status (276/277)](https://www.stedi.com/docs/healthcare/claim-status)
- [835 ERA Reports](https://www.stedi.com/docs/healthcare/era)
- [Insurance Discovery](https://www.stedi.com/docs/healthcare/insurance-discovery)
- [Payer Directory](https://www.stedi.com/docs/healthcare/payer-directory)

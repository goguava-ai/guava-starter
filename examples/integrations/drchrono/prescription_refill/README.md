# Prescription Refill

**Direction:** Inbound

A patient calls to request a prescription refill. The agent verifies their identity by email and date of birth, collects the medication and pharmacy details, and logs the refill request as a call log in DrChrono for the care team to act on.

## What it does

1. Collects patient email and looks up their record via `GET /patients?email={email}`
2. Collects date of birth for identity verification
3. Collects medication name, preferred pharmacy, and optional pharmacy phone
4. Asks if the patient has changed any other medications since their last visit
5. Documents the refill request via `POST /call_logs` for the care team to review and fulfill

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `DRCHRONO_ACCESS_TOKEN` | DrChrono OAuth2 Bearer token |
| `DRCHRONO_DOCTOR_ID` | Integer ID of the doctor (used for call log attribution) |
| `DRCHRONO_OFFICE_ID` | Integer ID of the office |

## Usage

```bash
export GUAVA_AGENT_NUMBER="+1..."
export DRCHRONO_ACCESS_TOKEN="..."
export DRCHRONO_DOCTOR_ID="123"
export DRCHRONO_OFFICE_ID="456"

python -m examples.integrations.drchrono.prescription_refill
```

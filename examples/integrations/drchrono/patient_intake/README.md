# Patient Intake

**Direction:** Inbound

A new patient calls to complete their intake before their first appointment at Oakridge Family Medicine. The agent collects demographics, insurance information, primary care concern, and known allergies, then creates a patient record in DrChrono.

## What it does

1. Collects first name, last name, date of birth, email, and cell phone
2. Optionally collects insurance carrier and member ID
3. Collects primary care concern and known allergies
4. Creates a patient record via `POST /patients`
5. Reads back the new patient ID so the caller can reference it

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `DRCHRONO_ACCESS_TOKEN` | DrChrono OAuth2 Bearer token |
| `DRCHRONO_DOCTOR_ID` | Integer ID of the doctor to associate the patient with |
| `DRCHRONO_OFFICE_ID` | Integer ID of the office |

## Usage

```bash
export GUAVA_AGENT_NUMBER="+1..."
export DRCHRONO_ACCESS_TOKEN="..."
export DRCHRONO_DOCTOR_ID="123"
export DRCHRONO_OFFICE_ID="456"

python -m examples.integrations.drchrono.patient_intake
```

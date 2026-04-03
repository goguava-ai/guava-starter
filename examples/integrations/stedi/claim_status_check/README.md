# Claim Status Check

**Direction:** Inbound

A patient calls billing to find out what happened to an insurance claim. The agent verifies their identity, collects their claim reference number, submits a real-time claim status inquiry (X12 276/277) to Stedi, and reads back the current processing status.

## What it does

1. Collects first name, last name, date of birth, member ID, payer, and claim number
2. Posts to `POST /change/medicalnetwork/claimstatus/v2`
3. Parses `claimStatus[].statusCategoryCode` and maps it to a human-readable description (e.g., `F2` = finalized, payment issued; `A7` = denied)
4. Includes adjudication date and check number/date if available
5. Reads back the status and offers to connect the patient to a billing specialist

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `STEDI_API_KEY` | Stedi API key |
| `STEDI_PROVIDER_NPI` | Provider NPI number |
| `STEDI_PROVIDER_NAME` | Provider organization name (optional) |

## Usage

```bash
python -m examples.integrations.stedi.claim_status_check
```

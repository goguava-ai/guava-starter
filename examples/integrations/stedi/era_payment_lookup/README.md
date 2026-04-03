# ERA Payment Lookup

**Direction:** Inbound

A billing staff member calls to retrieve payment details from an 835 electronic remittance advice (ERA). The agent collects the Stedi transaction ID and reads back the payer name, payment date, total amount, and a summary of claims covered.

## What it does

1. Collects the Stedi transaction ID from the caller
2. Calls `GET /change/medicalnetwork/reports/v2/{transactionId}/835`
3. Returns a 404-specific error message if the transaction ID is not found
4. Parses `financialInformation` for payment date, amount, and method
5. Parses `claimPaymentInformation[]` for per-claim billed/paid amounts
6. Reads back a summary and directs the caller to the Stedi portal for line-item detail

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `STEDI_API_KEY` | Stedi API key |

## Usage

```bash
python -m examples.integrations.stedi.era_payment_lookup
```

# Income Verification

**Direction:** Inbound

A customer calls to verify the income information on file for a loan or credit application. The agent retrieves payroll data from their connected account via Plaid and confirms the employer, pay frequency, and net pay with the customer.

## What it does

1. Loads payroll income data via `POST /credit/payroll_income/get` before the call begins
2. Reads back employer name, pay frequency, and most recent net pay to the customer
3. Records whether details are correct or captures a correction note for the loan officer

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `PLAID_CLIENT_ID` | Plaid client ID |
| `PLAID_SECRET` | Plaid secret key |

## Usage

```bash
python -m examples.integrations.plaid.income_verification
```

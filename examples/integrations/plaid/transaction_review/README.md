# Transaction Review

**Direction:** Inbound

A customer calls to review their recent transaction history. The agent loads the past 30 days of transactions via Plaid, summarizes spending by category, and walks the customer through their activity or searches for a specific transaction.

## What it does

1. Loads transactions via `POST /transactions/get` for the past 30 days before the call begins
2. Summarizes total spent, largest transaction, and top spending category
3. Lets the customer request a full summary, search for a specific transaction, or be redirected to the disputes team

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `PLAID_CLIENT_ID` | Plaid client ID |
| `PLAID_SECRET` | Plaid secret key |

## Usage

```bash
python -m examples.integrations.plaid.transaction_review
```

# Balance Inquiry

**Direction:** Inbound

A caller asks for their current bank account balance. The agent verifies their identity and fetches real-time balances using the Plaid Balance product.

## What it does

1. Collects name, account reference, and account type preference (checking / savings / all)
2. Resolves the caller's Plaid `access_token` from the application database
3. Fetches real-time balances via `POST /accounts/balance/get`
4. Reads back current and available balances for matching accounts

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `PLAID_CLIENT_ID` | Plaid client ID |
| `PLAID_SECRET` | Plaid secret |
| `PLAID_BASE_URL` | `https://sandbox.plaid.com` or `https://production.plaid.com` |
| `PLAID_TEST_ACCESS_TOKEN` | Test access token (sandbox only) |

## Usage

```bash
python -m examples.integrations.plaid.balance_inquiry
```

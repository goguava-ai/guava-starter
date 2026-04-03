# Account Verification

**Direction:** Inbound

A caller verifies their linked bank account. The agent collects their identity, looks up their Plaid access token from the application database, and reads back account details (type, mask, balance, routing number).

## What it does

1. Collects the caller's name and account reference (account number or email)
2. Resolves their Plaid `access_token` from the application database (via `lookup_access_token`)
3. Fetches account list via `POST /accounts/get`
4. Fetches ACH routing/account numbers via `POST /auth/get`
5. Reads back account type, mask, balance, and routing number (last 4 only for security)

## Note on `access_token`

Each user's Plaid `access_token` is obtained via the Link flow and stored in your application database. The `lookup_access_token` function in this example is a placeholder — replace it with a database lookup keyed on user ID or email.

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `PLAID_CLIENT_ID` | Plaid client ID |
| `PLAID_SECRET` | Plaid secret |
| `PLAID_BASE_URL` | `https://sandbox.plaid.com` or `https://production.plaid.com` |
| `PLAID_TEST_ACCESS_TOKEN` | Test access token (sandbox only; replace with DB lookup in production) |

## Usage

```bash
python -m examples.integrations.plaid.account_verification
```

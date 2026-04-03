# Plaid Integration

Voice agents that integrate with the [Plaid API](https://plaid.com/docs/api/) to support account verification, balance inquiries, transaction review, and income verification — for lending, fintech, and financial services applications.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`account_verification`](account_verification/) | Inbound | Caller verifies their linked bank account details |
| [`balance_inquiry`](balance_inquiry/) | Inbound | Caller asks for their current account balance |
| [`transaction_review`](transaction_review/) | Inbound | Caller asks about recent transactions on their account |
| [`income_verification`](income_verification/) | Inbound | Caller confirms income details during a loan or rental application |

## Authentication

All examples pass credentials in the request body (or optionally as headers):

```python
headers = {
    "PLAID-CLIENT-ID": os.environ["PLAID_CLIENT_ID"],
    "PLAID-SECRET": os.environ["PLAID_SECRET"],
    "Content-Type": "application/json",
}
```

All requests are `POST` with a JSON body. The `access_token` for each user is obtained via the Link flow and stored by your application.

## Base URL

| Environment | Base URL |
|---|---|
| Sandbox | `https://sandbox.plaid.com` |
| Production | `https://production.plaid.com` |

Set `PLAID_BASE_URL` to the appropriate environment.

## Common Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `PLAID_CLIENT_ID` | Plaid client ID |
| `PLAID_SECRET` | Plaid secret (environment-specific) |
| `PLAID_BASE_URL` | `https://sandbox.plaid.com` or `https://production.plaid.com` |

## Usage

All examples are inbound. The caller's `access_token` is looked up by your system using a customer identifier (e.g., email or account number) passed as an argument or resolved from your database.

```bash
python -m examples.integrations.plaid.account_verification
python -m examples.integrations.plaid.balance_inquiry
python -m examples.integrations.plaid.transaction_review
python -m examples.integrations.plaid.income_verification
```

## Plaid API Reference

- [Accounts](https://plaid.com/docs/api/accounts/)
- [Balance](https://plaid.com/docs/api/products/balance/)
- [Transactions](https://plaid.com/docs/api/products/transactions/)
- [Auth](https://plaid.com/docs/api/products/auth/)
- [Identity](https://plaid.com/docs/api/products/identity/)

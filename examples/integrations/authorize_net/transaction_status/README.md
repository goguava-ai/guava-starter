# Transaction Status

**Direction:** Inbound

A customer calls to check whether a payment went through. The agent collects their email and transaction ID, looks up the transaction in Authorize.net, and reads back the current status, settled amount, and submission date.

## What it does

1. Greets the caller as Alex from Pinnacle Payments
2. Collects the customer's email address
3. Collects the transaction ID (found on receipt emails or bank statements)
4. Calls `getTransactionDetailsRequest` with the provided transaction ID
5. Maps the raw status to a human-readable description (e.g. `settledSuccessfully` → "completed and settled")
6. Reads back the transaction status, amount, and date submitted
7. Asks if the customer has any other questions and responds accordingly

## Status Mapping

| Authorize.net Status | Spoken Description |
|---|---|
| `settledSuccessfully` | completed and settled |
| `authorizedPendingCapture` | authorized and pending capture |
| `declined` | declined |
| `voided` | voided |
| `refundSettledSuccessfully` | refunded and settled |
| `underReview` | currently under review |
| `pendingFinalSettlement` | pending final settlement |

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `AUTHNET_API_LOGIN_ID` | API Login ID from your Authorize.net account |
| `AUTHNET_TRANSACTION_KEY` | Transaction Key from your Authorize.net account |
| `AUTHNET_ENVIRONMENT` | `production` for live, omit for sandbox |

## Usage

```bash
python __main__.py
```

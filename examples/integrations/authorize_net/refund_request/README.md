# Refund Request

**Direction:** Inbound

A patient calls to request a refund on a settled transaction; the agent verifies the transaction and issues the refund via the Authorize.net API.

## What it does

1. Greets the caller as Maya from Crestview Dental billing support
2. Collects the transaction ID from the patient's receipt or billing statement
3. Collects the last four digits of the card used for the charge
4. Collects the reason for the refund
5. Asks the patient to confirm they want to proceed
6. Calls `getTransactionDetailsRequest` to verify the transaction exists and has a status of `settledSuccessfully`
7. Calls `createTransactionRequest` with `transactionType: refundTransaction` using the original settled amount
8. Reads back the refund confirmation number and informs the caller to expect 3–5 business days for the credit to appear

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `AUTHORIZENET_API_LOGIN_ID` | Authorize.net API Login ID |
| `AUTHORIZENET_TRANSACTION_KEY` | Authorize.net Transaction Key |

## Usage

```bash
python __main__.py
```

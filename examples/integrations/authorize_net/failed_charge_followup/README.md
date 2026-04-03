# Failed Charge Followup

**Direction:** Outbound

Proactively calls patients whose stored payment method was declined, offers to retry the charge immediately, or directs them to update their payment method.

## What it does

1. Pre-fetches the customer profile via `getCustomerProfileRequest` before dialing to retrieve the stored payment profile ID
2. Dials the patient and asks to speak with them by name
3. Explains that a recent payment of the specified amount was declined
4. Asks whether the patient was aware of the decline and the likely cause
5. Offers two resolution paths: retry the charge on the card currently on file, or update their payment method by calling the billing office
6. If the patient chooses to retry, calls `createTransactionRequest` with `transactionType: authCaptureTransaction` against the stored customer payment profile
7. Reads back the confirmation number on success, or provides the billing office number on failure
8. If the call is unanswered, leaves a professional voicemail with a callback number

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `AUTHORIZENET_API_LOGIN_ID` | Authorize.net API Login ID |
| `AUTHORIZENET_TRANSACTION_KEY` | Authorize.net Transaction Key |

## Usage

```bash
python __main__.py +15551234567 --customer-profile-id 12345678 --name "Jane Smith" --amount 125.00
```

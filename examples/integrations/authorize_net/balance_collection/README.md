# Balance Collection

**Direction:** Outbound

Proactively calls patients with an outstanding balance, confirms the amount owed, asks how they would like to pay, and processes payment against their stored payment profile.

## What it does

1. Pre-fetches the customer profile via `getCustomerProfileRequest` before dialing to retrieve the stored payment profile ID and card last four digits
2. Dials the patient and asks to speak with them by name
3. States the outstanding balance and asks the patient to confirm the amount is correct
4. Handles disputes or "already paid" responses by routing to the billing office
5. Offers payment options: charge the card on file, use a new card, mail a check, or request more time
6. Asks whether the patient wants to pay the full balance or a partial amount
7. Summarizes the payment and asks for confirmation before charging
8. Calls `createTransactionRequest` with `transactionType: authCaptureTransaction` against the stored customer payment profile
9. Reads back the confirmation number, notes any remaining balance, and confirms a receipt will be emailed
10. If the call is unanswered, leaves a professional voicemail with the balance and a callback number

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `AUTHORIZENET_API_LOGIN_ID` | Authorize.net API Login ID |
| `AUTHORIZENET_TRANSACTION_KEY` | Authorize.net Transaction Key |

## Usage

```bash
python __main__.py +15551234567 --customer-profile-id 12345678 --name "John Doe" --balance 350.00
```

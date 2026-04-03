# Payment Dispute

**Direction:** Inbound

Customers call about a disputed charge, and the agent explains the resolution process before optionally accepting liability on their behalf via the Adyen Disputes API.

## What it does

1. Greets the caller as Meridian Retail and identifies the disputed charge.
2. Collects the dispute PSP reference and the reason for the dispute.
3. Explains the dispute resolution process and typical timeline (5–10 business days).
4. Asks the customer whether they want to withdraw the dispute (accept liability) or continue with the review.
5. If the customer accepts liability, calls `POST /disputes/{disputePspReference}/accept` on the Adyen API.
6. Confirms the outcome and provides follow-up contact information either way.

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `ADYEN_API_KEY` | Adyen API key from the Customer Area |
| `ADYEN_MERCHANT_ACCOUNT` | Adyen merchant account name |

## Usage

```bash
python __main__.py
```

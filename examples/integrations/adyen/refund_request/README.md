# Refund Request

**Direction:** Inbound

Customers call in to request a refund on a recent order, and the agent collects the payment reference and refund details before submitting the refund via the Adyen Checkout API.

## What it does

1. Greets the caller as Northgate Commerce and identifies the need for a refund.
2. Collects the payment PSP reference (from the customer's receipt or confirmation email).
3. Collects the refund amount, currency, and reason for the refund.
4. Calls `POST /payments/{pspReference}/refunds` on the Adyen Checkout API to submit the refund.
5. Reads back the refund PSP reference and informs the customer of the expected timeline (3–5 business days).

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

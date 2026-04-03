# Fraud Alert Verification

**Direction:** Outbound

Meridian Commerce's fraud monitoring system flags a suspicious payment and triggers an outbound call to the cardholder to verify whether the transaction was authorized. If the customer confirms it was fraudulent, the agent immediately submits a reversal to Adyen via the Checkout API.

## What it does

1. Dials the customer and attempts to reach them directly using `reach_person`.
2. On contact: explains there is a flagged payment of the specified amount at the specified merchant and asks the customer if they recognize it.
3. Collects one of three responses: confirmed legitimate, denied (fraudulent), or unsure.
4. If legitimate: confirms no action is needed and ends the call.
5. If fraudulent: submits a reversal via `POST /payments/{pspReference}/reversals` and advises the customer to monitor their account and contact their bank.
6. If unsure: advises the customer to review their records and call back if needed.
7. If the customer does not answer: leaves an urgent voicemail requesting a callback.

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `ADYEN_API_KEY` | Adyen API key from the Customer Area |
| `ADYEN_MERCHANT_ACCOUNT` | Your Adyen merchant account name |
| `ADYEN_CHECKOUT_URL` | Checkout API base URL (default: `https://checkout-test.adyen.com/v71`) |

## Usage

```bash
python __main__.py +12125550100 \
  --name "Jane Smith" \
  --psp-reference "ABCD1234EFGH5678" \
  --amount '$149.99' \
  --merchant "Electronics Direct"
```

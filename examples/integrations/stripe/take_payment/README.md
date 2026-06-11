# Take Payment

**Direction:** Inbound

A customer calls to pay an amount over the phone. The agent collects the amount, confirms, texts a Stripe Checkout link to their phone, and voice-confirms as soon as Stripe reports the payment as paid — without ever handling card details on the call.

## What it does

1. Collects a payment amount and confirmation on the call; if caller-ID is blocked, also collects an SMS destination number
2. Creates a one-shot Stripe Checkout Session via `POST /v1/checkout/sessions`
3. Texts the hosted Checkout URL to the caller via `guava.Client().send_sms(...)`
4. Polls `GET /v1/checkout/sessions/{id}` on a background thread until `payment_status=paid`, the session expires, or a 180-second timeout fires
5. On success, hangs up with a spoken confirmation code derived from the Stripe `PaymentIntent` id

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number, also used as the SMS sender |
| `STRIPE_SECRET_KEY` | Stripe secret API key |
| `PAYMENT_SUCCESS_URL` | (Optional) Override for Checkout's required `success_url` (default: `https://goguava.ai`) |
| `PAYMENT_CANCEL_URL` | (Optional) Override for Checkout's required `cancel_url` (default: `https://goguava.ai`) |

## Usage

```bash
python __main__.py
```

# Payment Link Dispatch

**Direction:** Outbound

Meridian Commerce proactively calls a customer with an outstanding balance. Before dialing, the agent creates a secure Adyen payment link so it is ready to share the moment the customer answers. The agent gauges readiness to pay and either reads out the link, defers to email delivery, or escalates a dispute to the billing team.

## What it does

1. Creates an Adyen payment link via `POST /paymentLinks` before placing the call, set to expire in 24 hours.
2. Dials the customer and attempts to reach them directly using `reach_person`.
3. On contact: explains the outstanding balance and asks how they would like to proceed.
4. Collects one of three responses: ready to pay now, not right now, or want to dispute.
5. If ready to pay: reads the live payment link URL to the customer along with the expiry information.
6. If not right now: informs the customer a link will be sent to their email on file and expires in 24 hours.
7. If dispute: escalates to the billing team and assures the customer no payment is expected during review.
8. If the customer does not answer: leaves a voicemail noting the outstanding balance and that a link will arrive by email.

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
  --name "John Doe" \
  --amount "249.00" \
  --currency "USD" \
  --description "Invoice #INV-2026-0042" \
  --reference "INV-2026-0042"
```

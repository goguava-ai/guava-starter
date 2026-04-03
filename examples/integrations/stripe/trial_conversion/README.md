# Trial Conversion

**Direction:** Outbound

Call trial users a few days before their trial expires. The agent checks how the trial went, answers questions, and offers three paths: convert to paid immediately, let it convert automatically at trial end, or extend the trial by 7 days.

## What it does

1. Fetches the trialing subscription pre-call via `GET /v1/subscriptions?customer=...&status=trialing`
2. Reads trial end date, plan name, and billing amount to personalize the conversation
3. Based on the customer's decision:
   - **Convert now**: ends the trial immediately via `POST /v1/subscriptions/{id}` with `trial_end=now`
   - **Convert at trial end**: no change needed — Stripe handles this automatically
   - **Extend trial**: updates `trial_end` to +7 days via `POST /v1/subscriptions/{id}`
   - **Cancel**: no action — trial expires naturally

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `STRIPE_SECRET_KEY` | Stripe secret API key |

## Usage

```bash
python __main__.py +15551234567 --customer-id cus_abc123 --name "Jane Smith"
```

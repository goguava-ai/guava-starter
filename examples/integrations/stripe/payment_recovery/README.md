# Payment Recovery

**Direction:** Outbound

Call customers who have open (past-due) invoices. The agent explains the situation, understands why payment failed, and retries the charge if the customer confirms they've updated their payment method.

## What it does

1. Fetches open invoices pre-call via `GET /v1/invoices?customer=...&status=open`
2. Reaches the customer and discusses the payment issue
3. If they confirm their card is updated, retries each open invoice via `POST /v1/invoices/{id}/pay`

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `STRIPE_SECRET_KEY` | Stripe secret API key |

## Usage

```bash
python __main__.py +15551234567 --customer-id cus_abc123 --name "Jane Smith"
```

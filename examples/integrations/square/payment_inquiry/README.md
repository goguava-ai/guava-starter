# Payment Inquiry

**Direction:** Inbound

A customer calls to ask about a recent Square payment. The agent verifies their email, searches for their customer record, and lists recent transactions.

## What it does

1. Searches for the customer via `POST /v2/customers/search` (email filter)
2. Lists recent payments via `GET /v2/payments?customer_id=...`
3. Reads back the most recent payment amounts, dates, and statuses

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `SQUARE_ACCESS_TOKEN` | Square access token |
| `SQUARE_BASE_URL` | `https://connect.squareupsandbox.com` or `https://connect.squareup.com` |

## Usage

```bash
python -m examples.integrations.square.payment_inquiry
```

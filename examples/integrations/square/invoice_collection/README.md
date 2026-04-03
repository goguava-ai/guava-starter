# Invoice Collection

**Direction:** Outbound

Calls customers with unpaid Square invoices to collect payment. Fetches invoice details before the call, presents the amount and due date, and resends the invoice payment link if requested.

## What it does

1. Fetches invoice details via `GET /v2/invoices/{invoiceId}`
2. Calls the customer and presents the invoice amount and due date
3. Collects payment intent (paying today, this week, dispute, or resend)
4. If resend requested: publishes the invoice via `POST /v2/invoices/{invoiceId}/publish`

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `SQUARE_ACCESS_TOKEN` | Square access token |
| `SQUARE_BASE_URL` | `https://connect.squareupsandbox.com` or `https://connect.squareup.com` |

## Usage

```bash
python -m examples.integrations.square.invoice_collection "+15551234567" --name "Sam Nguyen" --invoice-id "inv:0-ChECARkSBqABACcQ"
```

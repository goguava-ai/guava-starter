# Square Payments Integration

Voice agents that integrate with the [Square API](https://developer.squareup.com/reference/square) to handle payment inquiries, refunds, invoice collection, and loyalty rewards — for retail, food service, and appointment-based businesses running on Square.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`payment_inquiry`](payment_inquiry/) | Inbound | Customer asks about a recent Square payment or transaction |
| [`refund_request`](refund_request/) | Inbound | Customer requests a refund; agent verifies the payment and creates a Square refund |
| [`invoice_collection`](invoice_collection/) | Outbound | Call customers with unpaid Square invoices; prompt payment confirmation |
| [`order_status`](order_status/) | Inbound | Customer asks about the status of a Square order |
| [`loyalty_rewards`](loyalty_rewards/) | Inbound | Customer asks about their loyalty points balance and reward status |

## Authentication

All examples use a Square access token passed as a Bearer token:

```python
headers = {
    "Authorization": f"Bearer {SQUARE_ACCESS_TOKEN}",
    "Square-Version": "2024-01-18",
    "Content-Type": "application/json",
}
```

Get your access token from the [Square Developer Dashboard](https://developer.squareup.com/apps).

## Base URL

| Environment | Base URL |
|---|---|
| Sandbox | `https://connect.squareupsandbox.com` |
| Production | `https://connect.squareup.com` |

Set `SQUARE_BASE_URL` to the appropriate environment.

## Common Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `SQUARE_ACCESS_TOKEN` | Square access token (sandbox or production) |
| `SQUARE_BASE_URL` | `https://connect.squareupsandbox.com` or `https://connect.squareup.com` |
| `SQUARE_LOCATION_ID` | Your Square location ID |

## Usage

Inbound examples:

```bash
python -m examples.integrations.square.payment_inquiry
python -m examples.integrations.square.refund_request
python -m examples.integrations.square.order_status
python -m examples.integrations.square.loyalty_rewards
```

Outbound example:

```bash
python -m examples.integrations.square.invoice_collection "+15551234567" --name "Sam Nguyen" --invoice-id "inv:0-ChECARkSBqABACcQ"
```

## Square API Reference

- [Payments](https://developer.squareup.com/reference/square/payments-api)
- [Refunds](https://developer.squareup.com/reference/square/refunds-api)
- [Orders](https://developer.squareup.com/reference/square/orders-api)
- [Invoices](https://developer.squareup.com/reference/square/invoices-api)
- [Customers](https://developer.squareup.com/reference/square/customers-api)
- [Loyalty](https://developer.squareup.com/reference/square/loyalty-api)

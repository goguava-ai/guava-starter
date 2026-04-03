# PayPal Integration

Voice agents that integrate with the [PayPal REST API](https://developer.paypal.com/api/rest/) to handle order status inquiries, refund requests, subscription questions, payment recovery, and dispute notifications — without routing customers to the PayPal portal or a live agent.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`order_status`](order_status/) | Inbound | Customer asks about the status of a PayPal order |
| [`refund_request`](refund_request/) | Inbound | Customer requests a refund on a captured PayPal payment |
| [`subscription_inquiry`](subscription_inquiry/) | Inbound | Customer asks about their billing plan, amount, and next payment date |
| [`payment_recovery`](payment_recovery/) | Outbound | Call customers with failed subscription billing; prompt to update payment method |
| [`dispute_notification`](dispute_notification/) | Outbound | Notify customers of an open dispute and collect resolution preference |

## Authentication

All examples use OAuth 2.0 client credentials to obtain a Bearer token:

```python
resp = requests.post(
    f"{BASE_URL}/v1/oauth2/token",
    data={"grant_type": "client_credentials"},
    auth=(PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET),
    headers={"Accept": "application/json"},
)
access_token = resp.json()["access_token"]
headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
```

## Base URL

| Environment | Base URL |
|---|---|
| Sandbox | `https://api-m.sandbox.paypal.com` |
| Production | `https://api-m.paypal.com` |

Set `PAYPAL_BASE_URL` to the appropriate environment.

## Common Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `PAYPAL_CLIENT_ID` | PayPal REST API client ID |
| `PAYPAL_CLIENT_SECRET` | PayPal REST API client secret |
| `PAYPAL_BASE_URL` | `https://api-m.sandbox.paypal.com` (sandbox) or `https://api-m.paypal.com` (production) |

## Usage

Inbound examples:

```bash
python -m examples.integrations.paypal.order_status
python -m examples.integrations.paypal.refund_request
python -m examples.integrations.paypal.subscription_inquiry
```

Outbound examples:

```bash
python -m examples.integrations.paypal.payment_recovery "+15551234567" --name "Jordan Lee" --subscription-id "I-BW452GLLEP1G"
python -m examples.integrations.paypal.dispute_notification "+15551234567" --name "Jordan Lee" --dispute-id "PP-D-27803"
```

## PayPal API Reference

- [Orders v2](https://developer.paypal.com/api/orders/v2/)
- [Payments v2](https://developer.paypal.com/api/payments/v2/)
- [Subscriptions v1](https://developer.paypal.com/api/subscriptions/v1/)
- [Disputes v1](https://developer.paypal.com/api/customer-disputes/v1/)

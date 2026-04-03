# Stripe Integration

Voice agents that integrate with the [Stripe API](https://docs.stripe.com/api) to handle subscription inquiries, cancellations, refunds, plan upgrades, and payment collection — without routing customers to a web portal or live agent.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`subscription_inquiry`](subscription_inquiry/) | Inbound | Customer asks about their plan, billing amount, and next renewal date |
| [`subscription_cancellation`](subscription_cancellation/) | Inbound | Customer cancels their subscription; agent captures reason and sets `cancel_at_period_end` |
| [`refund_request`](refund_request/) | Inbound | Customer requests a refund; agent verifies recent charges and creates a Stripe refund |
| [`plan_upgrade`](plan_upgrade/) | Inbound | Customer upgrades to a higher-tier plan; agent swaps the subscription price |
| [`payment_recovery`](payment_recovery/) | Outbound | Call customers with past-due invoices; retry payment if they confirm |
| [`churn_winback`](churn_winback/) | Outbound | Call recently canceled customers to gather feedback and gauge re-subscription interest |
| [`trial_conversion`](trial_conversion/) | Outbound | Call trial users nearing expiry; convert to paid by ending the trial early if they agree |

## Authentication

All examples use Stripe secret key HTTP Basic authentication:

```python
auth = (STRIPE_SECRET_KEY, "")   # key as username, empty password
```

Get your secret key in the Stripe Dashboard: **Developers** → **API keys**. Use `sk_test_...` for testing and `sk_live_...` for production.

## Request Format

Stripe accepts **form-encoded** request bodies (not JSON). All `POST` requests use `data={}`, not `json={}`.

## Common Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `STRIPE_SECRET_KEY` | Stripe secret API key (`sk_test_...` or `sk_live_...`) |

## Stripe API Reference

- [Customers](https://docs.stripe.com/api/customers)
- [Subscriptions](https://docs.stripe.com/api/subscriptions)
- [Invoices](https://docs.stripe.com/api/invoices)
- [Charges](https://docs.stripe.com/api/charges)
- [Refunds](https://docs.stripe.com/api/refunds)

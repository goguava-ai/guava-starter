# Chargebee Integration

Voice agents that integrate with the [Chargebee API](https://apidocs.chargebee.com/docs/api) to handle subscription inquiries, cancellations, plan upgrades, payment recovery, and trial conversions — without routing customers to a billing portal or live agent.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`subscription_inquiry`](subscription_inquiry/) | Inbound | Customer asks about their plan, billing amount, and next renewal date |
| [`subscription_cancellation`](subscription_cancellation/) | Inbound | Customer cancels; agent captures reason and schedules end-of-term cancellation |
| [`plan_upgrade`](plan_upgrade/) | Inbound | Customer upgrades to a higher tier; agent changes the subscription plan |
| [`payment_recovery`](payment_recovery/) | Outbound | Call customers with dunning invoices; collect payment method update intent |
| [`trial_conversion`](trial_conversion/) | Outbound | Call trial users nearing expiry; convert to paid if they agree |

## Authentication

All examples use HTTP Basic Auth with the Chargebee API key as the username and an empty password:

```python
AUTH = (os.environ["CHARGEBEE_API_KEY"], "")
```

Get your API key from **Settings → API Keys** in the Chargebee dashboard.

## Base URL

```
https://{site}.chargebee.com/api/v2
```

Set `CHARGEBEE_SITE` to your site subdomain (e.g., `mycompany-test` for test, `mycompany` for production).

## Common Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `CHARGEBEE_SITE` | Your Chargebee site subdomain |
| `CHARGEBEE_API_KEY` | Chargebee API key |

## Usage

Inbound examples:

```bash
python -m examples.integrations.chargebee.subscription_inquiry
python -m examples.integrations.chargebee.subscription_cancellation
python -m examples.integrations.chargebee.plan_upgrade
```

Outbound examples:

```bash
python -m examples.integrations.chargebee.payment_recovery "+15551234567" --name "Morgan Blake" --subscription-id "AzZlGKSoMz5b3Bkm1"
python -m examples.integrations.chargebee.trial_conversion "+15551234567" --name "Morgan Blake" --subscription-id "AzZlGKSoMz5b3Bkm1" --trial-end "March 30, 2026"
```

## Request Format

Chargebee accepts **form-encoded** request bodies for POST/PUT requests:

```python
requests.post(url, auth=AUTH, data={"reason_code": "not_needed"})
```

## Chargebee API Reference

- [Subscriptions](https://apidocs.chargebee.com/docs/api/subscriptions)
- [Customers](https://apidocs.chargebee.com/docs/api/customers)
- [Invoices](https://apidocs.chargebee.com/docs/api/invoices)
- [Credit Notes](https://apidocs.chargebee.com/docs/api/credit_notes)

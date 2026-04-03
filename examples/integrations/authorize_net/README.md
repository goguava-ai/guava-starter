# Authorize.net Integration

Voice agents that integrate with the [Authorize.net API](https://developer.authorize.net/api/reference/) to handle refund requests, payment plan enrollment, failed charge recovery, and balance collection.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`refund_request`](refund_request/) | Inbound | Patient calls to request a refund on a settled transaction; agent verifies and issues the refund |
| [`payment_plan_enrollment`](payment_plan_enrollment/) | Inbound | Patient calls to set up a recurring monthly payment plan for an outstanding balance |
| [`failed_charge_followup`](failed_charge_followup/) | Outbound | Agent calls patients whose stored payment was declined and offers to retry or redirect |
| [`balance_collection`](balance_collection/) | Outbound | Agent calls patients with an outstanding balance and processes payment against their stored profile |

## Authentication

All requests POST to the same endpoint. Merchant authentication is embedded in every request body:

```python
"merchantAuthentication": {"name": API_LOGIN_ID, "transactionKey": TRANSACTION_KEY}
```

Use the sandbox endpoint (`apitest.authorize.net`) for development.

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `AUTHORIZENET_API_LOGIN_ID` | Authorize.net API Login ID |
| `AUTHORIZENET_TRANSACTION_KEY` | Authorize.net Transaction Key |

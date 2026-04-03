# Subscription Inquiry

**Direction:** Inbound

A customer calls to ask about their PayPal subscription — plan, billing amount, and next payment date. The agent collects their subscription ID and looks it up via the PayPal Subscriptions API.

## What it does

1. Collects the caller's email and subscription ID
2. Fetches subscription details via `GET /v1/billing/subscriptions/{subscriptionId}`
3. Reads back status, plan ID, last payment amount, next billing date, and any failed payments

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `PAYPAL_CLIENT_ID` | PayPal REST API client ID |
| `PAYPAL_CLIENT_SECRET` | PayPal REST API client secret |
| `PAYPAL_BASE_URL` | `https://api-m.sandbox.paypal.com` or `https://api-m.paypal.com` |

## Usage

```bash
python -m examples.integrations.paypal.subscription_inquiry
```

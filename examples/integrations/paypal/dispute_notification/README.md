# Dispute Notification

**Direction:** Outbound

Calls a customer to notify them about an open PayPal dispute on their account, collects their preferred resolution, and coordinates next steps.

## What it does

1. Fetches dispute details via `GET /v1/customer/disputes/{disputeId}`
2. Calls the customer and explains the dispute reason and amount
3. Determines if the customer filed the dispute or if it may be fraudulent
4. Captures resolution preference (refund, replacement, escalate as fraud)

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `PAYPAL_CLIENT_ID` | PayPal REST API client ID |
| `PAYPAL_CLIENT_SECRET` | PayPal REST API client secret |
| `PAYPAL_BASE_URL` | `https://api-m.sandbox.paypal.com` or `https://api-m.paypal.com` |

## Usage

```bash
python -m examples.integrations.paypal.dispute_notification "+15551234567" --name "Jordan Lee" --dispute-id "PP-D-27803"
```

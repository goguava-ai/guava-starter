# Subscription Management

**Direction:** Inbound

A customer calls to manage their Authorize.net ARB (Automated Recurring Billing) subscription. The agent looks up the subscription, reads back the plan details, and can process a cancellation on the spot. Pause and payment method update requests are directed to the account portal or billing team, as those actions are not supported in this voice flow.

## What it does

1. Greets the caller as Riley from Pinnacle Payments
2. Collects the customer's email address
3. Collects the subscription ID (found in confirmation emails)
4. Calls `ARBGetSubscriptionRequest` to fetch current subscription details
5. Reads back the plan name, billing amount, billing interval, status, and estimated next billing date
6. Asks what the customer would like to do (cancel, pause, check billing date, update payment method, or just checking)
7. If cancelling: confirms intent, then calls `ARBCancelSubscriptionRequest`
8. If pausing or updating payment method: explains those actions require the account portal or billing team
9. If just checking: thanks the caller and ends the call

## Action Handling

| Customer Choice | Outcome |
|---|---|
| cancel my subscription | Confirms intent, then cancels via `ARBCancelSubscriptionRequest` |
| pause my subscription | Directs to account portal or billing team |
| check billing date | Reads estimated next billing date and ends call |
| update payment method | Directs to account portal or billing team |
| nothing, just checking | Thanks caller and ends call |

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `AUTHNET_API_LOGIN_ID` | API Login ID from your Authorize.net account |
| `AUTHNET_TRANSACTION_KEY` | Transaction Key from your Authorize.net account |
| `AUTHNET_ENVIRONMENT` | `production` for live, omit for sandbox |

## Usage

```bash
python __main__.py
```

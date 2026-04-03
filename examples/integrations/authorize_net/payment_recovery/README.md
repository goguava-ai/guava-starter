# Payment Recovery

**Direction:** Outbound

Calls customers whose Authorize.net ARB subscription payment has failed and their account is suspended. The agent explains the situation, determines why the payment failed, and either guides the customer to update their payment method, advises them the retry will happen automatically once the card is updated, or cancels the subscription at the customer's request.

## What it does

1. Before the call: fetches the subscription via `ARBGetSubscriptionRequest` to confirm suspended status and retrieve the customer profile ID
2. Attempts to reach the customer by name; falls back to a voicemail if unavailable
3. Introduces as Casey from Pinnacle Payments and explains the failed payment
4. Collects whether the customer was aware of the issue
5. Collects the likely cause of the payment failure (expired card, changed card, insufficient funds, bank block, not sure)
6. Collects whether they've already updated their payment method or want to cancel
7. Based on response:
   - **Updated card**: advises that Authorize.net will retry automatically within 24–48 hours; provides the account portal URL
   - **Not yet updated**: directs them to the account portal to update their payment method
   - **Cancel**: calls `ARBCancelSubscriptionRequest` and confirms cancellation
8. If no answer: leaves a professional voicemail with the portal URL

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `AUTHNET_API_LOGIN_ID` | API Login ID from your Authorize.net account |
| `AUTHNET_TRANSACTION_KEY` | Transaction Key from your Authorize.net account |
| `AUTHNET_ENVIRONMENT` | `production` for live, omit for sandbox |

## Usage

```bash
python __main__.py +15551234567 \
  --name "Jane Smith" \
  --email "jane@example.com" \
  --subscription-id "12345" \
  --amount "49.99"
```

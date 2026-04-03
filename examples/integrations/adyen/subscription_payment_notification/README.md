# Subscription Payment Notification

**Direction:** Outbound

Meridian Retail proactively calls customers before a large recurring subscription payment processes, confirms they are aware of the upcoming charge, answers questions about their plan, and captures any changes they want to make before the renewal date.

## What it does

1. Pre-fetches the customer's stored recurring payment details from the Adyen Recurring API (`POST /listRecurringDetails`) to reference their payment method by name during the call.
2. Calls the customer and reaches them by name using `reach_person`.
3. Notifies the customer of the upcoming charge amount, plan name, scheduled date, and payment method on file.
4. Asks if they were aware of the charge and whether they have any questions about their plan.
5. Captures the customer's desired action: proceed, update payment method, change plan, or cancel before renewal.
6. Provides tailored next steps and self-service links for each outcome.
7. Leaves a friendly voicemail with renewal details if the customer is unavailable.

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `ADYEN_API_KEY` | Adyen API key from the Customer Area |
| `ADYEN_MERCHANT_ACCOUNT` | Adyen merchant account name |

## Usage

```bash
python __main__.py +12125550100 \
  --name "James Okafor" \
  --shopper-reference "shopper-james-99" \
  --plan "Pro Annual" \
  --amount "299.00" \
  --currency USD \
  --charge-date "April 15th"
```

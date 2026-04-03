# Failed Payment Recovery

**Direction:** Outbound

Northgate Commerce proactively calls customers whose most recent payment was declined, checks for stored payment methods on file, and guides them to update their billing details online.

## What it does

1. Pre-fetches the customer's stored payment methods from the Adyen Recurring API (`POST /listRecurringDetails`) before placing the call.
2. Calls the customer and reaches them by name using `reach_person`.
3. Informs the customer that their recent payment was declined and whether saved payment methods are on file.
4. Asks whether they can update their payment method online, use a different card, need more time, or want to cancel.
5. Provides the appropriate next steps for each response, directing card updates to the secure self-service portal.
6. Leaves a voicemail if the customer is unavailable.

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `ADYEN_API_KEY` | Adyen API key from the Customer Area |
| `ADYEN_MERCHANT_ACCOUNT` | Adyen merchant account name |

## Usage

```bash
python __main__.py +12125550100 \
  --name "Jane Smith" \
  --shopper-reference "shopper-jane-42" \
  --amount "89.99" \
  --currency USD
```

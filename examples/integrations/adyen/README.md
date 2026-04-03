# Adyen Integration

Voice agents that integrate with the [Adyen API](https://docs.adyen.com/api-explorer/) to handle refund requests, payment disputes, failed payment recovery, and proactive billing notifications.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`refund_request`](refund_request/) | Inbound | Customer calls to request a refund; agent collects the payment reference and submits a refund via the Adyen Checkout API. |
| [`payment_dispute`](payment_dispute/) | Inbound | Customer calls about a disputed charge; agent explains the resolution process and optionally accepts liability via the Adyen Disputes API. |
| [`failed_payment_recovery`](failed_payment_recovery/) | Outbound | Agent calls customers whose payment was declined, checks stored payment methods on file, and directs them to update their billing details. |
| [`subscription_payment_notification`](subscription_payment_notification/) | Outbound | Agent proactively calls customers before a large recurring charge, confirms awareness, answers plan questions, and captures any changes before the renewal date. |

## Authentication

All examples use Adyen's `X-API-Key` header. Use test endpoints (`checkout-test.adyen.com`, `pal-test.adyen.com`) for development and switch to your live subdomain-based URLs for production.

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `ADYEN_API_KEY` | Adyen API key from the Customer Area |
| `ADYEN_MERCHANT_ACCOUNT` | Adyen merchant account name |

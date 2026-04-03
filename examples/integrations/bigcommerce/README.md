# BigCommerce Integration

Voice agents that integrate with the [BigCommerce REST API](https://developer.bigcommerce.com/docs/rest-management/orders) to handle order inquiries, refunds, proactive order issue resolution, and abandoned cart recovery.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`order_status_inquiry`](order_status_inquiry/) | Inbound | Customer calls to check their order status; agent looks up their account by email and reads back the current status and tracking info. |
| [`refund_request`](refund_request/) | Inbound | Customer calls to request a refund; agent verifies the order, checks eligibility, and posts the refund via the API. |
| [`order_issue_followup`](order_issue_followup/) | Outbound | Agent calls customers whose orders are flagged (backorder, missing item, payment issue), explains the problem, and updates order status based on their choice. |
| [`abandoned_cart_recovery`](abandoned_cart_recovery/) | Outbound | Agent calls customers who left items in their cart, references their specific products, optionally applies a discount, and helps them complete the purchase. |

## Authentication

All examples use the `X-Auth-Token` header with a store-level API key.

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `BIGCOMMERCE_STORE_HASH` | Your BigCommerce store hash (from the store URL) |
| `BIGCOMMERCE_ACCESS_TOKEN` | API access token from BigCommerce Advanced Settings → API Accounts |

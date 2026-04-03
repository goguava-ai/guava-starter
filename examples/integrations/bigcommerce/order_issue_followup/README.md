# Order Issue Followup

**Direction:** Outbound

Crestline Outdoor Gear proactively calls a customer whose order has been flagged with a problem (backorder, missing item, or payment failure), explains the situation, presents resolution options, and updates the order status in BigCommerce based on their choice.

## What it does

1. Pre-fetches the order via `GET /v2/orders/{id}` before placing the call.
2. Places an outbound call and uses `reach_person` to confirm the customer is live on the line.
3. On success, introduces the agent as Sierra from Crestline Outdoor Gear and explains the specific issue.
4. Presents resolution choices appropriate to the issue type:
   - **backorder** — wait, cancel and refund, or ship available items now.
   - **missing_item** — send the missing item, partial refund, or full return.
   - **payment_issue** — update payment method or cancel order.
5. Updates the order's `status_id` via `PUT /v2/orders/{id}` based on the customer's choice.
6. On voicemail (`on_failure`), leaves a concise message with the issue summary and a callback number.

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `BIGCOMMERCE_STORE_HASH` | Your BigCommerce store hash (from the store URL) |
| `BIGCOMMERCE_ACCESS_TOKEN` | API access token from BigCommerce Advanced Settings → API Accounts |

## Usage

```bash
export GUAVA_AGENT_NUMBER="+15551234567"
export BIGCOMMERCE_STORE_HASH="abc123"
export BIGCOMMERCE_ACCESS_TOKEN="your_token_here"

python __main__.py "+12125550101" --order-id 10042 --name "Jordan Lee" --issue backorder
python __main__.py "+12125550101" --order-id 10055 --name "Sam Rivera" --issue missing_item
python __main__.py "+12125550101" --order-id 10067 --name "Alex Kim" --issue payment_issue
```

Use `--help` to see all options:

```bash
python __main__.py --help
```

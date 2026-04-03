# Abandoned Cart Recovery

**Direction:** Outbound

Maple & Co. proactively calls a customer who left items in their cart, references the specific products waiting for them, offers an optional discount, and helps them complete the purchase or routes the call appropriately based on their response.

## What it does

1. Pre-fetches the abandoned cart via `GET /v2/abandoned-carts/{cart_id}` and builds a plain-English item summary before placing the call.
2. Places an outbound call and uses `reach_person` to confirm the customer is live on the line.
3. On success, introduces the agent as Evelyn from Maple & Co., mentions the specific items left in the cart, and optionally flags that a discount code is available.
4. Asks the customer how they'd like to proceed (multiple choice):
   - **Complete purchase now** — reads back the checkout URL from the cart's `redirect_urls`.
   - **Apply discount and complete purchase** — calls `POST /v2/carts/{cart_id}/coupons` to apply the code, then provides the checkout URL.
   - **Need help with an item** — informs the customer a product specialist will follow up within 24 hours.
   - **No longer interested** — thanks them and closes warmly.
5. On voicemail (`on_failure`), leaves a brief friendly message noting the cart is saved and optionally mentioning the discount code.

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

# Without a discount code
python __main__.py "+12125550101" --name "Jane Doe" --cart-id "abc-cart-token-123"

# With a discount code
python __main__.py "+12125550101" --name "Jane Doe" --cart-id "abc-cart-token-123" --discount-code "COMEBACK10"
```

Use `--help` to see all options:

```bash
python __main__.py --help
```

# Product Inquiry

**Direction:** Inbound

A customer calls Harbor House to ask about a product. The agent finds out what they're looking for and what they want to know, searches the BigCommerce catalog in real time, and reads back the relevant details — availability, price, description, or variant options — then offers to help them order or transfer to a specialist.

## What it does

1. Accepts the inbound call and greets the customer as Casey from Harbor House.
2. Collects the product name the customer is asking about.
3. Collects the inquiry type via multiple choice: stock check, price, product details, or size/color options.
4. Searches the BigCommerce catalog via `GET /v3/catalog/products?name=<product_name>&include=variants`.
5. Maps the `availability` field and `inventory_level` to a friendly label (in stock, out of stock, available for pre-order, currently unavailable).
6. Reads back the relevant detail based on what the customer asked: availability, price, cleaned product description, or variant option list.
7. Asks whether the customer would like to order, is just browsing, or wants to be transferred to a specialist.
8. Routes the hangup instructions accordingly.

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `BIGCOMMERCE_STORE_HASH` | Your BigCommerce store hash (from the store URL) |
| `BIGCOMMERCE_AUTH_TOKEN` | API access token from the BigCommerce control panel |

## Usage

```bash
export GUAVA_AGENT_NUMBER="+1..."
export BIGCOMMERCE_STORE_HASH="abc123"
export BIGCOMMERCE_AUTH_TOKEN="your_token_here"

python -m examples.integrations.bigcommerce.product_inquiry
```

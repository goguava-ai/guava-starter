# Shopify Integration

Voice agents that integrate with the [Shopify Admin REST API](https://shopify.dev/docs/api/admin-rest) to handle order status checks, cancellations, returns, abandoned cart recovery, and shipping updates — for e-commerce brands running on Shopify.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`order_status`](order_status/) | Inbound | Customer asks about order status, tracking, or estimated delivery |
| [`order_cancellation`](order_cancellation/) | Inbound | Customer cancels an order that hasn't shipped yet |
| [`return_request`](return_request/) | Inbound | Customer initiates a return; agent captures reason and item details |
| [`abandoned_cart_recovery`](abandoned_cart_recovery/) | Outbound | Call customers with abandoned checkouts to recover the sale |
| [`shipping_update`](shipping_update/) | Outbound | Proactively notify customers of shipping delays or delivery confirmation |

## Authentication

All examples use the `X-Shopify-Access-Token` header:

```python
headers = {
    "X-Shopify-Access-Token": os.environ["SHOPIFY_ACCESS_TOKEN"],
    "Content-Type": "application/json",
}
```

For private apps, use your Admin API access token. For public apps, use the OAuth access token obtained during installation.

## Base URL

```
https://{store}.myshopify.com/admin/api/2026-01
```

Set `SHOPIFY_STORE` to your store subdomain (e.g., `mykestrelgoods`).

## Common Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `SHOPIFY_STORE` | Your Shopify store subdomain (without `.myshopify.com`) |
| `SHOPIFY_ACCESS_TOKEN` | Admin API access token |

## Usage

Inbound examples:

```bash
python -m examples.integrations.shopify.order_status
python -m examples.integrations.shopify.order_cancellation
python -m examples.integrations.shopify.return_request
```

Outbound examples:

```bash
python -m examples.integrations.shopify.abandoned_cart_recovery "+15551234567" --name "Taylor Kim" --checkout-id "1053844928" --cart-value "89.95"
python -m examples.integrations.shopify.shipping_update "+15551234567" --name "Taylor Kim" --order-id "5678901234" --order-name "#1042"
```

## Shopify API Reference

- [Orders](https://shopify.dev/docs/api/admin-rest/2026-01/resources/order)
- [Refunds](https://shopify.dev/docs/api/admin-rest/2026-01/resources/refund)
- [Customers](https://shopify.dev/docs/api/admin-rest/2026-01/resources/customer)
- [Checkouts](https://shopify.dev/docs/api/admin-rest/2026-01/resources/abandoned-checkouts)
- [Fulfillments](https://shopify.dev/docs/api/admin-rest/2026-01/resources/fulfillment)

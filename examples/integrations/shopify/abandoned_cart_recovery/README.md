# Abandoned Cart Recovery

**Direction:** Outbound

An outbound call is placed to a customer who left items in their Shopify cart. The agent loads the cart details, discusses the abandoned items, addresses any questions, and optionally sends a recovery email with a link back to the cart.

## What it does

1. Loads the abandoned checkout via `GET /admin/api/2026-01/checkouts/{token}.json`
2. Calls the customer and discusses their cart contents
3. Optionally sends a recovery email via `POST /admin/api/2026-01/checkouts/{token}/send_invoice.json`

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `SHOPIFY_STORE` | Shopify store subdomain |
| `SHOPIFY_ACCESS_TOKEN` | Admin API access token |

## Usage

```bash
python -m examples.integrations.shopify.abandoned_cart_recovery \
  --checkout-token abc123 \
  --customer-name "Jamie" \
  --phone "+15551234567"
```

# Magento / Adobe Commerce Integration

Voice agents that integrate with the [Magento REST API](https://developer.adobe.com/commerce/webapi/rest/) to handle order inquiries, returns, product availability checks, and order cancellations — all over the phone.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`order_status`](order_status/) | Inbound | Customer calls to check order status by order number or email |
| [`return_request`](return_request/) | Inbound | Customer calls to initiate a return or exchange; creates an RMA in Magento |
| [`product_availability`](product_availability/) | Inbound | Customer calls to check whether a product is in stock |
| [`order_cancellation`](order_cancellation/) | Inbound | Customer calls to cancel an unshipped order; confirms before executing |

## Authentication

All examples use an admin integration access token, passed as a Bearer token:

```
Authorization: Bearer {MAGENTO_ACCESS_TOKEN}
```

Generate a token in Magento Admin: **System** → **Extensions** → **Integrations** → **Add New Integration** → **API** tab → select resources → Activate.

## Common Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `MAGENTO_BASE_URL` | Your store's base URL (e.g. `https://mystore.com`) |
| `MAGENTO_ACCESS_TOKEN` | Admin integration access token |

## Magento REST API Reference

- [Orders](https://developer.adobe.com/commerce/webapi/rest/tutorials/orders/)
- [Returns (RMA)](https://developer.adobe.com/commerce/webapi/rest/modules/sales/rma/)
- [Products](https://developer.adobe.com/commerce/webapi/rest/tutorials/configurable-product/)
- [Inventory / Stock Items](https://developer.adobe.com/commerce/webapi/rest/inventory/)

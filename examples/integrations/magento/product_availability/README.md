# Product Availability — Magento / Adobe Commerce Integration

An inbound voice agent that checks product availability and stock status. Customers can search by product name or provide a SKU for an exact match.

## How It Works

**1. Collect the product query**

The agent asks what product the caller is looking for and whether they have a SKU.

**2. Search or fetch the product**

- By SKU: `GET /rest/V1/products/{sku}` for an exact match
- By name: `GET /rest/V1/products?searchCriteria[...][name]=like:%{query}%`

**3. Check stock status**

`get_product_stock()` calls `GET /rest/V1/stockItems/{sku}` to retrieve `is_in_stock` and `qty` fields.

**4. Respond to the caller**

The agent reports whether the item is in stock (with a low-stock quantity note if under 10 units), out of stock, or not found. Out-of-stock callers are directed to website restock notifications.

## Magento API Calls

| Timing | Method | Endpoint | Purpose |
|---|---|---|---|
| Mid-call | `GET` | `/rest/V1/products` | Search products by name |
| Mid-call | `GET` | `/rest/V1/products/{sku}` | Fetch product by exact SKU |
| Mid-call | `GET` | `/rest/V1/stockItems/{sku}` | Check stock quantity and availability |

## Setup

```bash
export GUAVA_AGENT_NUMBER="+1..."
export MAGENTO_BASE_URL="https://mystore.com"
export MAGENTO_ACCESS_TOKEN="..."
```

## Run

```bash
python -m examples.integrations.magento.product_availability
```

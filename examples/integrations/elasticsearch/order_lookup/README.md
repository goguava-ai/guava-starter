# Order Lookup

**Direction:** Inbound

A customer calls to look up their order status. The agent queries an Elasticsearch orders index by email or order number and reads back the order status, total, shipping status, and tracking number.

## What it does

1. Collects customer email and optional order number
2. Searches by order number via `term` query on `order_number.keyword`, or by email via `term` on `customer_email.keyword`
3. Reads back order status, item count, total, shipping status, and tracking number

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `ELASTICSEARCH_URL` | Elasticsearch cluster URL |
| `ELASTICSEARCH_API_KEY` | Elasticsearch API key |
| `ELASTICSEARCH_ORDER_INDEX` | Index name (default: `orders`) |

## Usage

```bash
python -m examples.integrations.elasticsearch.order_lookup
```

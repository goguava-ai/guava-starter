# Product Search

**Direction:** Inbound

A customer calls to search for products. The agent collects a search query, optional price limit, and category filter, then queries Elasticsearch using a `multi_match` query with fuzziness and reads back the top results.

## What it does

1. Collects search query, optional max price, and optional category
2. Searches via `POST /{index}/_search` with a `bool` query combining `multi_match` and range/term filters
3. Reads back up to 3 matching products with name, price, category, and stock status

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `ELASTICSEARCH_URL` | Elasticsearch cluster URL |
| `ELASTICSEARCH_API_KEY` | Elasticsearch API key |
| `ELASTICSEARCH_PRODUCT_INDEX` | Index name (default: `products`) |

## Usage

```bash
python -m examples.integrations.elasticsearch.product_search
```

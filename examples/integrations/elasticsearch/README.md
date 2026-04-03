# Elasticsearch / Elastic Cloud Integration

Voice agents that integrate with the [Elasticsearch REST API](https://www.elastic.co/docs/api/doc/elasticsearch/) to power conversational search over products, orders, knowledge base articles, and logs — for teams running Elasticsearch or Elastic Cloud.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`product_search`](product_search/) | Inbound | Caller searches for products by description; agent returns top matches and pricing |
| [`order_lookup`](order_lookup/) | Inbound | Caller looks up an order by name or ID from an orders index |
| [`knowledge_base_query`](knowledge_base_query/) | Inbound | Caller asks a support question; agent searches a knowledge base index and reads back the answer |
| [`log_inquiry`](log_inquiry/) | Inbound | Internal caller queries recent error logs or alert events by keyword |

## Authentication

All examples use an Elastic Cloud API key in the `Authorization` header:

```python
headers = {
    "Authorization": f"ApiKey {os.environ['ELASTICSEARCH_API_KEY']}",
    "Content-Type": "application/json",
}
```

Create an API key in **Elastic Cloud → Security → API Keys** or via `POST /_security/api_key`.

## Base URL

```
https://{deployment_id}.{region}.gcp.elastic-cloud.com:9243
```

For self-managed clusters, use your cluster's HTTP endpoint. Set `ELASTIC_BASE_URL` to the full base URL.

## Common Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `ELASTICSEARCH_URL` | Elasticsearch cluster base URL |
| `ELASTICSEARCH_API_KEY` | Elastic Cloud or cluster API key |

## Usage

All examples are inbound:

```bash
python -m examples.integrations.elasticsearch.product_search
python -m examples.integrations.elasticsearch.order_lookup
python -m examples.integrations.elasticsearch.knowledge_base_query
python -m examples.integrations.elasticsearch.log_inquiry
```

## Elasticsearch API Reference

- [Search API](https://www.elastic.co/docs/api/doc/elasticsearch/operation/operation-search)
- [Get Document](https://www.elastic.co/docs/api/doc/elasticsearch/operation/operation-get)
- [Index Document](https://www.elastic.co/docs/api/doc/elasticsearch/operation/operation-index)
- [Bulk API](https://www.elastic.co/docs/api/doc/elasticsearch/operation/operation-bulk)

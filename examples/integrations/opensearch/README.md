# OpenSearch Integration

Voice agents that integrate with [OpenSearch](https://opensearch.org/docs/latest/) to search knowledge bases, product catalogs, and document stores in real time during calls — and to index call outcomes for downstream analysis.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`knowledge_base_search`](knowledge_base_search/) | Inbound | Agent searches an OpenSearch knowledge base to answer customer questions |
| [`product_catalog_search`](product_catalog_search/) | Inbound | Customer describes a product; agent searches the catalog and reads back matches |
| [`call_transcript_indexer`](call_transcript_indexer/) | Inbound | After the call, structured call data is indexed into OpenSearch for reporting |

## Authentication

All examples use HTTP Basic authentication:

```python
from opensearchpy import OpenSearch

client = OpenSearch(
    hosts=[{"host": OPENSEARCH_HOST, "port": int(OPENSEARCH_PORT)}],
    http_auth=(OPENSEARCH_USER, OPENSEARCH_PASSWORD),
    use_ssl=True,
    verify_certs=True,
)
```

## Common Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `OPENSEARCH_HOST` | OpenSearch cluster hostname |
| `OPENSEARCH_PORT` | OpenSearch port (default: `443` for managed, `9200` for self-hosted) |
| `OPENSEARCH_USER` | Username (or `admin` for local) |
| `OPENSEARCH_PASSWORD` | Password |

## OpenSearch API Reference

- [Search API](https://docs.opensearch.org/latest/api-reference/search-apis/search/)
- [Index Document](https://docs.opensearch.org/latest/api-reference/document-apis/index-document/)
- [Query DSL](https://docs.opensearch.org/latest/query-dsl/)

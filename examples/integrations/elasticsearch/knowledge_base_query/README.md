# Knowledge Base Query

**Direction:** Inbound

A customer calls with a support question. The agent searches an Elasticsearch knowledge base index using `multi_match` with highlighting and reads back the most relevant article excerpt and URL.

## What it does

1. Collects the customer's question
2. Searches via `POST /{index}/_search` with `multi_match` across title, content, and tags fields
3. Uses Elasticsearch highlighting to extract a relevant content snippet
4. Reads back the top article title, excerpt, and URL

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `ELASTICSEARCH_URL` | Elasticsearch cluster URL |
| `ELASTICSEARCH_API_KEY` | Elasticsearch API key |
| `ELASTICSEARCH_KB_INDEX` | Knowledge base index name (default: `knowledge_base`) |

## Usage

```bash
python -m examples.integrations.elasticsearch.knowledge_base_query
```

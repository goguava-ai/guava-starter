# Zendesk Help Center RAG Example

Inbound voice agent that answers questions from your **Zendesk Help Center**. Published articles are fetched at startup via the Zendesk v2 REST API, stripped of HTML, and indexed into `DocumentQA` backed by `LanceDBStore`.

No SDK required — the Zendesk API is called directly with `requests` and Basic Auth.

## How it works

```
Startup:
  Zendesk Help Center API ──► GET /api/v2/help_center/articles
          ──► strip HTML bodies ──► DocumentQA (LanceDBStore, Vertex AI embeddings)

Caller asks a question
        │
        ▼
┌──────────────────────────────────────┐
│  LanceDBStore (VectorStore)          │
│                                      │
│  Vertex AI embeds query (768-dim) ─┐ │
│                                    │ │
│  HNSW cosine similarity search ◄───┘ │
│  ──► matching article chunks         │
└──────────────────────────────────────┘
        │
        ▼
  DocumentQA.ask()
  (Gemini 2.5 Flash answers from chunks)
        │
        ▼
  Answer spoken to caller
```

## Running

```bash
export ZENDESK_SUBDOMAIN="mycompany"
export ZENDESK_EMAIL="agent@mycompany.com"
export ZENDESK_API_TOKEN="your-api-token"

python -m examples.rag."examples of integrations".zendesk_rag
```

Requires `GUAVA_API_KEY`, `GUAVA_AGENT_NUMBER`, and GCP credentials for Vertex AI (`GOOGLE_CLOUD_PROJECT`).

On first run, articles are fetched from Zendesk, embedded, and stored in `lancedb_data/`. Subsequent runs skip re-ingestion if data already exists.

## Environment variables

| Variable | Description |
|---|---|
| `ZENDESK_SUBDOMAIN` | Your Zendesk subdomain (e.g. `mycompany` for `mycompany.zendesk.com`) |
| `ZENDESK_EMAIL` | Zendesk agent email address |
| `ZENDESK_API_TOKEN` | Zendesk API token (Admin Center > Apps & Integrations > Zendesk API) |
| `GUAVA_API_KEY` | Guava platform API key |
| `GUAVA_AGENT_NUMBER` | Inbound phone number |
| `GOOGLE_CLOUD_PROJECT` | GCP project for Vertex AI |

## Pagination

The example fetches up to 100 articles (one page). For larger Help Centers, follow the `next_page` cursor in the response:

```python
url = f"https://{subdomain}.zendesk.com/api/v2/help_center/articles"
while url:
    resp = requests.get(url, params={"per_page": 100}, auth=(...))
    articles.extend(resp.json()["articles"])
    url = resp.json()["next_page"]
```

## Dependencies

- `requests` — HTTP client for Zendesk REST API calls
- `google-genai` — Vertex AI embedding (768-dim) and Gemini answer generation

## Key files

| File | Purpose |
|---|---|
| `__main__.py` | `ZendeskController` — fetches articles via REST API, indexes into LanceDB |
| `guava/helpers/rag/` | `DocumentQA`, `LanceDBStore`, `VectorStore` — SDK RAG helpers |

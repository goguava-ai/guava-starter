# Kustomer Knowledge Base RAG Example

Inbound voice agent that answers questions from your **Kustomer** knowledge base. Published articles are fetched at startup via the Kustomer v3 REST API and indexed into `DocumentQA` backed by `LanceDBStore`.

No SDK required — the Kustomer API is called directly with `requests` and a Bearer token. Among the three knowledge base examples, this is the simplest: Kustomer returns plain text content so no HTML stripping is needed.

## How it works

```
Startup:
  Kustomer API ──► GET /p/v3/kb/articles
          ──► DocumentQA (LanceDBStore, Vertex AI embeddings)

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
export KUSTOMER_API_KEY="your-api-key"

python -m examples.rag."examples of integrations".kustomer_rag
```

Requires `GUAVA_API_KEY`, `GUAVA_AGENT_NUMBER`, and GCP credentials for Vertex AI (`GOOGLE_CLOUD_PROJECT`).

On first run, articles are fetched from Kustomer, embedded, and stored in `lancedb_data/`. Subsequent runs skip re-ingestion if data already exists.

## Environment variables

| Variable | Description |
|---|---|
| `KUSTOMER_API_KEY` | Kustomer API key (Settings > Security > API Keys) |
| `GUAVA_API_KEY` | Guava platform API key |
| `GUAVA_AGENT_NUMBER` | Inbound phone number |
| `GOOGLE_CLOUD_PROJECT` | GCP project for Vertex AI |

## Dependencies

- `requests` — HTTP client for Kustomer REST API calls
- `google-genai` — Vertex AI embedding (768-dim) and Gemini answer generation

## Key files

| File | Purpose |
|---|---|
| `__main__.py` | `KustomerController` — fetches articles via REST API, indexes into LanceDB |
| `guava/helpers/rag/` | `DocumentQA`, `LanceDBStore`, `VectorStore` — SDK RAG helpers |

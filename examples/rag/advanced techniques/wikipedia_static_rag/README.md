# Insurance Q&A — Static Wikipedia RAG Example

Inbound voice agent that answers general insurance questions using Wikipedia articles as its knowledge base. At startup it fetches a fixed list of Wikipedia articles, embeds them with Vertex AI into `LanceDBStore`, and answers questions via `DocumentQA`.

## How it works

```
Startup:
  Fetch articles from Wikipedia API
            │
            ▼
    DocumentQA(documents=articles, store=LanceDBStore(...))
    ──► chunk_document() ──► Vertex AI embed ──► LanceDB

Caller asks a question
        │
        ▼
  DocumentQA.ask()
  ──► embed query (Vertex AI)
  ──► cosine search (LanceDB)
  ──► Gemini 2.5 Flash answers from top chunks
        │
        ▼
  Answer spoken to caller
```

No API key is needed for Wikipedia — only Vertex AI (embedding + generation) requires GCP credentials.

## Articles indexed

The default configuration indexes these Wikipedia articles:

- Homeowner's insurance
- Flood insurance
- Earthquake insurance
- Insurance policy
- Deductible
- Actual cash value
- Replacement cost
- Subrogation

To change the knowledge base, edit the `WIKI_ARTICLES` list in `__main__.py`.

## Key difference from `hybrid_rag`

| | `hybrid_rag` | `wikipedia_static_rag` |
|---|---|---|
| Documents | Local `.txt` files | Wikipedia articles (fetched at startup) |
| Startup | Fast | Slower (HTTP + embedding on first run) |
| Knowledge | Domain-specific policy docs | General insurance concepts |

## Running

```bash
python -m examples.rag.local.wikipedia_static_rag
```

Requires `GUAVA_API_KEY`, `GUAVA_AGENT_NUMBER`, and GCP credentials for Vertex AI (`GOOGLE_CLOUD_PROJECT`).

## Dependencies

Included via `pip install 'gridspace-guava[lancedb]'`:

- `lancedb` — local vector database for article storage
- `httpx` — fetches Wikipedia articles via REST API
- `google-genai` — Vertex AI embedding and Gemini answer generation

## Key files

| File | Purpose |
|------|---------|
| `__main__.py` | `WikipediaQAController` + `fetch_wikipedia_article()` — fetches articles and builds `DocumentQA` + `LanceDBStore` |
| `guava/helpers/rag/` | `DocumentQA`, `LanceDBStore` — SDK RAG helpers |

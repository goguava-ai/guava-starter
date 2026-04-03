# Open Q&A — Dynamic Wikipedia RAG Example

Inbound voice agent that answers any general knowledge question by searching Wikipedia in real time. Unlike `wikipedia_static_rag` which pre-fetches a fixed list of articles, this example dynamically searches Wikipedia for every question — covering any topic without a predefined knowledge base.

## How it works

```
Caller asks a question
        │
        ▼
  _rewrite_query()
  (Gemini rewrites follow-ups into standalone queries)
        │
        ▼
  Try answering from per-call LanceDBStore
  (articles already fetched during this conversation)
        │
   +---------+-----------+
   |                     |
   v                     v
sufficient          insufficient / empty
   |                     │
   v                     v
answer             DynamicWikipediaRetriever
caller             ──► Wikipedia API search
                   ──► fetch article text
                   ──► LanceDBStore.add_texts()
                   ──► search + answer
```

The example uses a "cache-first" strategy: follow-up questions are checked against articles already fetched during the conversation (stored in a per-call `LanceDBStore`) before triggering a new Wikipedia search. This avoids redundant lookups and supports natural follow-up chains like "What is earthquake insurance?" → "What about in Japan?" → "And Canada?"

Gemini checks if the cached context is sufficient (returning `NEED_MORE_INFO` if not) before fetching new articles, keeping the number of API calls minimal.

## Key differences from `wikipedia_static_rag`

| | `wikipedia_static_rag` | `wikipedia_dynamic_rag` |
|---|---|---|
| Articles | Fixed list, fetched at startup | Searched live per question |
| Index | Shared across all calls | Per-call (isolated `LanceDBStore`) |
| Follow-ups | Stateless | Gemini rewrites using conversation history |
| Startup time | Slow (fetch + embed all articles) | Instant |
| Coverage | Only pre-configured topics | All of Wikipedia |

## Running

```bash
python -m examples.rag.local.wikipedia_dynamic_rag
```

Requires `GUAVA_API_KEY`, `GUAVA_AGENT_NUMBER`, and GCP credentials for Vertex AI (`GOOGLE_CLOUD_PROJECT`).

## Dependencies

Included via `pip install 'gridspace-guava[lancedb]'`:

- `lancedb` — per-call vector store (temporary directory, isolated per conversation)
- `httpx` — searches and fetches Wikipedia articles via REST API
- `google-genai` — Vertex AI embedding, Gemini query rewriting and answer generation

## Key files

| File | Purpose |
|------|---------|
| `__main__.py` | `WikipediaOpenQAController` + `DynamicWikipediaRetriever` — dynamic Wikipedia search, per-call `LanceDBStore`, Gemini query rewriting and answer generation |
| `guava/helpers/rag/` | `LanceDBStore`, `chunk_document` — SDK RAG helpers |

# Insurance Policy Q&A — Contextual Retrieval RAG Example

Inbound voice agent that answers policyholder questions using **Anthropic's Contextual Retrieval** technique. Before indexing, each chunk is enriched with a Claude-generated context summary that helps the retriever understand what the chunk is about — significantly improving retrieval accuracy for ambiguous queries.

## How it works

```
  Documents loaded from docs/
            │
            ▼
    chunk_document()
    (split into overlapping chunks)
            │
            ▼
┌───────────────────────────────────────────┐
│      contextualize_chunks()               │
│                                           │
│  For each chunk:                          │
│    Claude reads full document (cached)    │
│    + the individual chunk                 │
│    → generates a short context summary    │
│    → prepends it to the chunk             │
│                                           │
│  "This chunk discusses the water damage   │
│   exclusion in Section 4..."              │
│  + original chunk text                    │
└───────────────────────────────────────────┘
            │
            ▼
    LanceDBStore.add_texts()
    (Vertex AI embeds enriched chunks, stores in LanceDB)
            │
            ▼
  Caller asks a question ──► LanceDBStore.search()
            │
            ▼
  Gemini 2.5 Flash generates answer from top chunks
```

**Without contextual enrichment**, a chunk about "Section 4 exclusions" might not match a query about "water damage" if it doesn't contain those exact words. **With contextual enrichment**, Claude's prepended summary explicitly mentions "water damage exclusion" — giving the semantic retriever a much better signal.

Uses Anthropic **prompt caching** so the full document is sent as a cached system message and processed once. Each chunk's contextualization is then a cheap follow-up call against the cached input.

## Key differences from `hybrid_rag`

| | `hybrid_rag` | `contextual_rag` |
|---|---|---|
| Chunk content | Raw document text | Claude-generated context + raw text |
| Embedding | Vertex AI (768-dim) | Vertex AI (768-dim, same) |
| Startup time | Fast (just embedding) | Slower (one Claude call per chunk) |
| Retrieval accuracy | Good | Better for ambiguous/indirect queries |
| Extra dependency | None | `anthropic` (Anthropic API key required) |
| Cost | Embedding + Gemini only | Embedding + Gemini + Claude Haiku at index time |

## Documents

Policy knowledge is stored as plain text files in `docs/`. All `.txt` files are loaded, chunked, contextualized, and indexed at startup.

| File | Contents |
|------|----------|
| `policy_coverages.txt` | Coverages A–F, deductibles, exclusions |
| `endorsements_and_addons.txt` | Scheduled property, water backup, earthquake, flood, home business |
| `claims_process.txt` | Filing steps, timelines, dispute resolution, FAQ |
| `discounts_and_pricing.txt` | Rating factors, available discounts, premium calculation example |
| `cancellation_and_renewal.txt` | Cancellation, nonrenewal, reinstatement, payment options |

## Running

```bash
python -m examples.rag.local.contextual_rag
```

Requires `GUAVA_API_KEY`, `GUAVA_AGENT_NUMBER`, `ANTHROPIC_API_KEY`, and GCP credentials for Vertex AI (`GOOGLE_CLOUD_PROJECT`).

## Dependencies

- `anthropic` — Anthropic Python SDK for Claude calls during chunk contextualization
- `lancedb` — local vector database (`pip install 'gridspace-guava[lancedb]'`)
- `google-genai` — Vertex AI embedding and Gemini answer generation

## Key files

| File | Purpose |
|------|---------|
| `__main__.py` | `ContextualPolicyQAController` + `contextualize_chunks()` — chunk enrichment with Claude, LanceDB indexing, Gemini answer generation |
| `guava/helpers/rag/` | `LanceDBStore`, `chunk_document` — SDK RAG helpers |

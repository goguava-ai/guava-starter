# Insurance Policy Q&A — Custom Embedding and Generation Models

Inbound voice agent that answers policyholder questions using fully custom embedding and generation models. Demonstrates how to replace Guava's built-in Vertex AI defaults with any third-party provider by subclassing `EmbeddingModel` and `GenerationModel`.

This example uses **OpenAI** for embedding and **Anthropic Claude** for answer generation — neither requires Guava or GCP credentials.

## How it works

```
Documents loaded from docs/
        │
        ▼
  LanceDBStore(embedding_model=OpenAIEmbedding())
        │
        ├── OpenAI text-embedding-3-large (3072-dim)
        │   embeds chunks at index time
        │
        └── HNSW cosine search over stored vectors
        │
        ▼
  Caller asks a question ──► DocumentQA.ask()
        │
        ├── OpenAIEmbedding.embed_query()
        │   embeds the query
        │
        ├── LanceDBStore.search()
        │   returns top-k matching chunks
        │
        └── ClaudeGeneration.generate()
            Claude Haiku produces the answer
        │
        ▼
  Answer spoken to caller
```

## Custom model implementations

### `OpenAIEmbedding(EmbeddingModel)`

Subclasses `EmbeddingModel` and implements `embed()` and `ndims()`. Because `embed_documents()` and `embed_query()` both default to calling `embed()`, only one method needs to be implemented for a model that uses the same call for both.

### `ClaudeGeneration(GenerationModel)`

Subclasses `GenerationModel` and implements `generate()`. The `system_instruction` kwarg maps directly to Anthropic's `system` parameter.

## Comparison with default configuration

| | Default (`document_qa/`) | This example |
|---|---|---|
| Embedding | Vertex AI `gemini-embedding-001` (768-dim) | OpenAI `text-embedding-3-large` (3072-dim) |
| Generation | Gemini 2.5 Flash | Claude Haiku |
| Vector store | LanceDB on GCS | LanceDB local |
| Extra credentials | GCP only | `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` |

## Documents

Policy knowledge is stored as plain text files in `docs/`. All `.txt` files are loaded and indexed at startup.

| File | Contents |
|------|----------|
| `policy_coverages.txt` | Coverages A–F, deductibles, exclusions |
| `endorsements_and_addons.txt` | Scheduled property, water backup, earthquake, flood, home business |
| `claims_process.txt` | Filing steps, timelines, dispute resolution, FAQ |
| `discounts_and_pricing.txt` | Rating factors, available discounts, premium calculation example |
| `cancellation_and_renewal.txt` | Cancellation, nonrenewal, reinstatement, payment options |

## Running

```bash
python -m examples.rag.advanced_techniques.custom_models_rag
```

Requires `GUAVA_AGENT_NUMBER`, `OPENAI_API_KEY`, and `ANTHROPIC_API_KEY`.

## Dependencies

```bash
pip install 'gridspace-guava[lancedb]' openai anthropic
```

- `lancedb` — local vector database
- `openai` — OpenAI Python SDK for embeddings
- `anthropic` — Anthropic Python SDK for answer generation

## Key files

| File | Purpose |
|------|---------|
| `__main__.py` | `OpenAIEmbedding`, `ClaudeGeneration`, `CustomModelsPolicyQAController` — full custom model wiring |
| `guava/helpers/rag/embedding.py` | `EmbeddingModel` ABC to subclass |
| `guava/helpers/rag/generation.py` | `GenerationModel` ABC to subclass |

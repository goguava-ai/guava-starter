# Insurance Policy Q&A — ChromaDB RAG Example

Inbound voice agent that answers policyholder questions using **ChromaDB** as a persistent local vector database. `ChromaVectorStore` implements the `guava.helpers.rag.VectorStore` ABC, making ChromaDB a drop-in backend for `DocumentQA`.

ChromaDB handles embedding internally using its built-in model (`all-MiniLM-L6-v2`) — no Vertex AI call is needed for indexing or search. Gemini via Vertex AI is used only for the final answer generation step.

## How it works

```
Caller asks a question
        │
        ▼
┌─────────────────────────────────────────┐
│  ChromaVectorStore(VectorStore)         │
│                                         │
│  ChromaDB embeds query automatically    │
│  (all-MiniLM-L6-v2, built-in)          │
│  ──► cosine similarity search           │
│  ──► top-k chunks                       │
└─────────────────────────────────────────┘
        │
        ▼
  DocumentQA.ask()
  (Gemini 2.5 Flash answers from chunks)
        │
        ▼
  Answer spoken to caller
```

`ChromaVectorStore` subclasses `VectorStore` and wraps ChromaDB's collection API. This shows how to plug any vector database into `DocumentQA` — implement four methods (`add_texts`, `search`, `clear`, `count`) and it works.

## Key differences from `hybrid_rag`

| | `hybrid_rag` (LanceDB) | `chromadb_rag` |
|---|---|---|
| Embedding | Vertex AI (768-dim) | ChromaDB built-in (384-dim) |
| Storage | LanceDB file | ChromaDB on-disk (SQLite + HNSW) |
| Shared across processes | No | No |
| VectorStore pattern | `LanceDBStore` (built-in) | `ChromaVectorStore` (custom ABC impl) |

## Documents

Policy knowledge is stored as plain text files in `docs/`. All `.txt` files are loaded and indexed on first run.

| File | Contents |
|------|----------|
| `policy_coverages.txt` | Coverages A–F, deductibles, exclusions |
| `endorsements_and_addons.txt` | Scheduled property, water backup, earthquake, flood, home business |
| `claims_process.txt` | Filing steps, timelines, dispute resolution, FAQ |
| `discounts_and_pricing.txt` | Rating factors, available discounts, premium calculation example |
| `cancellation_and_renewal.txt` | Cancellation, nonrenewal, reinstatement, payment options |

To re-index after document changes: delete the `chroma_data/` directory and restart.

## Running

```bash
python -m examples.rag.hosted.chromadb_rag
```

Requires `GUAVA_API_KEY`, `GUAVA_AGENT_NUMBER`, and GCP credentials for Vertex AI (`GOOGLE_CLOUD_PROJECT`).

On first run, ChromaDB creates a `chroma_data/` directory alongside the example. Subsequent runs load the existing collection instantly.

## Dependencies

- `chromadb` — local persistent vector database with built-in embedding

## Key files

| File | Purpose |
|------|---------|
| `__main__.py` | `ChromaPolicyQAController` + `ChromaVectorStore(VectorStore)` — ChromaDB setup and VectorStore ABC implementation |
| `guava/helpers/rag/` | `DocumentQA`, `VectorStore` — SDK RAG helpers |

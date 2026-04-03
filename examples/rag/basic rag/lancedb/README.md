# Insurance Policy Q&A — LanceDB RAG Example

Inbound voice agent for **Keystone Property & Casualty** that answers policyholder questions using `DocumentQA` with `LanceDBStore`. Documents are chunked, embedded with Vertex AI, and stored in LanceDB at startup. Subsequent calls are answered in milliseconds from the persisted index.

## How it works

```
Caller asks a question
        │
        ▼
┌─────────────────────────────────────────┐
│           LanceDBStore                  │
│                                         │
│  Vertex AI embeds query ──────────────┐ │
│  (gemini-embedding-001, 768-dim)      │ │
│                                       │ │
│  HNSW cosine search ──► top-k chunks  │ │
└─────────────────────────────────────────┘
        │
        ▼
  DocumentQA.ask()
  (Gemini 2.5 Flash answers from chunks)
        │
        ▼
  Answer spoken to caller
```

Documents are embedded once at startup using Vertex AI. On subsequent restarts, `DocumentQA` detects that the index is already populated and skips re-embedding. When `docs/` changes, delete the `lancedb_data/` directory to force re-indexing.

## Documents

Policy knowledge is stored as plain text files in `docs/`. All `.txt` files are loaded and indexed at startup.

| File | Contents |
|------|----------|
| `policy_coverages.txt` | Coverages A–F, deductibles, exclusions |
| `endorsements_and_addons.txt` | Scheduled property, water backup, earthquake, flood, home business |
| `claims_process.txt` | Filing steps, timelines, dispute resolution, FAQ |
| `discounts_and_pricing.txt` | Rating factors, available discounts, premium calculation example |
| `cancellation_and_renewal.txt` | Cancellation, nonrenewal, reinstatement, payment options |

To add knowledge, drop a new `.txt` file into `docs/` and restart.

## Running

```bash
python -m examples.rag.local.hybrid_rag
```

Requires `GUAVA_API_KEY`, `GUAVA_AGENT_NUMBER`, and GCP credentials for Vertex AI (`GOOGLE_CLOUD_PROJECT`).

## Dependencies

Included via `pip install 'gridspace-guava[lancedb]'`:

- `lancedb` — local vector database (file-based, no server required)
- `google-genai` — Vertex AI embedding and Gemini answer generation

## Key files

| File | Purpose |
|------|---------|
| `__main__.py` | `PolicyQAController` — loads docs, builds `DocumentQA` + `LanceDBStore`, answers questions |
| `guava/helpers/rag/` | `DocumentQA`, `LanceDBStore`, `chunk_document` — SDK RAG helpers |

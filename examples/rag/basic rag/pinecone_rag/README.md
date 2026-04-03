# Insurance Policy Q&A — Pinecone RAG Example

Inbound voice agent that answers policyholder questions using **Pinecone** as a cloud-hosted vector database. `PineconeVectorStore` implements the `guava.helpers.rag.VectorStore` ABC — documents are embedded with Vertex AI and upserted to a Pinecone serverless index.

Unlike LanceDB (local files), the Pinecone index is accessible from anywhere and survives process restarts — ideal for production deployments where multiple agents share the same knowledge base.

## How it works

```
Startup (first run):
  Documents ──► chunk_document() ──► Vertex AI embed (768-dim)
           ──► Pinecone upsert (vectors + chunk text as metadata)

Caller asks a question
        │
        ▼
┌─────────────────────────────────────────┐
│  PineconeVectorStore(VectorStore)       │
│                                         │
│  Vertex AI embeds query (768-dim) ────┐ │
│                                       │ │
│  Pinecone cosine similarity search ◄──┘ │
│  ──► chunk text from metadata           │
└─────────────────────────────────────────┘
        │
        ▼
  DocumentQA.ask()
  (Gemini 2.5 Flash answers from chunks)
        │
        ▼
  Answer spoken to caller
```

## Key differences from `chromadb_rag`

| | ChromaDB (local) | Pinecone (cloud) |
|---|---|---|
| Hosting | Local on-disk | Cloud managed service |
| Embedding | ChromaDB built-in (384-dim) | Vertex AI (768-dim) |
| Shared across instances | No | Yes |
| Scaling | Single-machine | Managed serverless |
| Auth | None | `PINECONE_API_KEY` |
| Cost | Free | Pinecone pricing (free tier available) |

## Documents

Policy knowledge is stored as plain text files in `docs/`. All `.txt` files are embedded and upserted to Pinecone on first run.

| File | Contents |
|------|----------|
| `policy_coverages.txt` | Coverages A–F, deductibles, exclusions |
| `endorsements_and_addons.txt` | Scheduled property, water backup, earthquake, flood, home business |
| `claims_process.txt` | Filing steps, timelines, dispute resolution, FAQ |
| `discounts_and_pricing.txt` | Rating factors, available discounts, premium calculation example |
| `cancellation_and_renewal.txt` | Cancellation, nonrenewal, reinstatement, payment options |

## Running

```bash
export PINECONE_API_KEY="your-pinecone-api-key"

python -m examples.rag.hosted.pinecone_rag
```

Requires `GUAVA_API_KEY`, `GUAVA_AGENT_NUMBER`, `PINECONE_API_KEY`, and GCP credentials for Vertex AI (`GOOGLE_CLOUD_PROJECT`).

On first run the example creates a serverless Pinecone index (`policy-documents`, 768-dim) and upserts all chunks. Subsequent runs skip ingestion if the index already has vectors.

## Dependencies

- `pinecone` — Pinecone Python client
- `google-genai` — Vertex AI embedding (768-dim) and Gemini answer generation

## Key files

| File | Purpose |
|------|---------|
| `__main__.py` | `PineconePolicyQAController` + `PineconeVectorStore(VectorStore)` — Pinecone index setup, Vertex AI embedding, VectorStore ABC implementation |
| `guava/helpers/rag/` | `DocumentQA`, `VectorStore` — SDK RAG helpers |

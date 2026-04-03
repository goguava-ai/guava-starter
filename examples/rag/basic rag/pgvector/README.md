# Insurance Policy Q&A — pgvector RAG Example

Inbound voice agent for **Keystone Property & Casualty** that answers policyholder questions using `DocumentQA` with `PgVectorStore`. Documents are embedded with Vertex AI and stored in a PostgreSQL table using the `pgvector` extension.


## How it works

```
Caller asks a question
        │
        ▼
┌─────────────────────────────────────────┐
│           PgVectorStore                 │
│                                         │
│  Vertex AI embeds query ──────────────┐ │
│                                       │ │
│  HNSW cosine search via pgvector      │ │
│  SELECT … ORDER BY embedding <=> $1   │ │
│  LIMIT k ──► top-k chunks             │ │
└─────────────────────────────────────────┘
        │
        ▼
  DocumentQA.ask()
  (Gemini 2.5 Flash answers from chunks)
        │
        ▼
  Answer spoken to caller
```

On first run `PgVectorStore` creates the `vector` extension and a `guava_chunks` table with an HNSW index automatically. `DocumentQA` detects the populated table on subsequent restarts and skips re-embedding.

## Documents

Policy knowledge is stored as plain text files in `docs/`. All `.txt` files are loaded and indexed on first run.

| File | Contents |
|------|----------|
| `policy_coverages.txt` | Coverages A–F, deductibles, exclusions |
| `endorsements_and_addons.txt` | Scheduled property, water backup, earthquake, flood, home business |
| `claims_process.txt` | Filing steps, timelines, dispute resolution, FAQ |
| `discounts_and_pricing.txt` | Rating factors, available discounts, premium calculation example |
| `cancellation_and_renewal.txt` | Cancellation, nonrenewal, reinstatement, payment options |

To re-index after document changes: `DELETE FROM guava_chunks;` and restart.

## Running

Start a local Postgres with pgvector using Docker:

```bash
docker run -d -p 5432:5432 \
    -e POSTGRES_PASSWORD=pass \
    pgvector/pgvector:pg16
```

Then run the example:

```bash
export DATABASE_URL="postgresql://postgres:pass@localhost:5432/postgres"

python -m examples.rag.local.pgvector_rag
```

Requires `GUAVA_API_KEY`, `GUAVA_AGENT_NUMBER`, `DATABASE_URL`, and GCP credentials for Vertex AI (`GOOGLE_CLOUD_PROJECT`).

## Dependencies

Installed via `pip install 'gridspace-guava[pgvector]'`:

- `psycopg[binary]` — PostgreSQL async driver
- `pgvector` — pgvector Python client (`register_vector`, numpy array support)
- `google-genai` — Vertex AI embedding and Gemini answer generation

## Key files

| File | Purpose |
|------|---------|
| `__main__.py` | `PolicyQAController` — loads docs, builds `DocumentQA` + `PgVectorStore`, answers questions |
| `guava/helpers/rag/` | `DocumentQA`, `PgVectorStore`, `chunk_document` — SDK RAG helpers |

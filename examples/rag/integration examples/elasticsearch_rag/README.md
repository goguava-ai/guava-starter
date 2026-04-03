# Insurance Policy Q&A — Elasticsearch RAG Example

Inbound voice agent that answers policyholder questions using **Elasticsearch** with hybrid BM25 + kNN search. `ElasticsearchVectorStore` implements the `guava.helpers.rag.VectorStore` ABC — documents are embedded with Vertex AI and stored in Elasticsearch with both their text (for BM25) and their embedding (for kNN).

At query time, both searches run in parallel and results are merged using Elasticsearch's native **Reciprocal Rank Fusion** via the `sub_searches` + `rank` API — no client-side score merging needed.

## How it works

```
Caller asks a question
        │
        ▼
  Vertex AI embeds query (768-dim)
        │
        ▼
┌─────────────────────────────────────────┐
│  ElasticsearchVectorStore(VectorStore)  │
│                                         │
│  sub_searches:                          │
│    BM25 (match on "text") ──────────┐   │
│    kNN  (cosine on "embedding") ────┤   │
│                                     │   │
│  rank: { rrf }  ◄───────────────────┘   │
│  (Reciprocal Rank Fusion, server-side)  │
│                                         │
│  ──► merged top-k chunks                │
└─────────────────────────────────────────┘
        │
        ▼
  DocumentQA.ask()
  (Gemini 2.5 Flash answers from chunks)
        │
        ▼
  Answer spoken to caller
```

## Key differences from other examples

| | `hybrid_rag` (LanceDB) | `elasticsearch_rag` | `opensearch_rag` |
|---|---|---|---|
| BM25 + kNN fusion | Vector search only | Server-side RRF (`rank` API) | Server-side (Search Pipeline) |
| Embedding | Vertex AI (client-side) | Vertex AI (client-side) | OpenSearch model (server-side) |
| Persistence | Local file | Elasticsearch index | OpenSearch index |
| Infra | None | Self-hosted or Elastic Cloud | AWS managed |

## Documents

Policy knowledge is stored as plain text files in `docs/`. All `.txt` files are embedded and indexed on first run.

| File | Contents |
|------|----------|
| `policy_coverages.txt` | Coverages A–F, deductibles, exclusions |
| `endorsements_and_addons.txt` | Scheduled property, water backup, earthquake, flood, home business |
| `claims_process.txt` | Filing steps, timelines, dispute resolution, FAQ |
| `discounts_and_pricing.txt` | Rating factors, available discounts, premium calculation example |
| `cancellation_and_renewal.txt` | Cancellation, nonrenewal, reinstatement, payment options |

To re-index: `curl -X DELETE localhost:9200/policy-documents` and restart.

## Running

Start Elasticsearch locally with Docker:

```bash
docker run -d -p 9200:9200 \
    -e "discovery.type=single-node" \
    -e "xpack.security.enabled=false" \
    elasticsearch:8.15.0
```

Then run the example:

```bash
python -m examples.rag.hosted.elasticsearch_rag
```

Requires `GUAVA_API_KEY`, `GUAVA_AGENT_NUMBER`, and GCP credentials for Vertex AI (`GOOGLE_CLOUD_PROJECT`). Optionally set `ELASTICSEARCH_URL` (defaults to `http://localhost:9200`).

## Dependencies

- `elasticsearch` — Elasticsearch Python client
- `google-genai` — Vertex AI embedding (768-dim) and Gemini answer generation

## Key files

| File | Purpose |
|------|---------|
| `__main__.py` | `ElasticsearchPolicyQAController` + `ElasticsearchVectorStore(VectorStore)` — index setup, Vertex AI embedding, hybrid BM25+kNN search |
| `guava/helpers/rag/` | `DocumentQA`, `VectorStore` — SDK RAG helpers |

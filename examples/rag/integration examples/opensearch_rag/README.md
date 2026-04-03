# Insurance Policy Q&A — Amazon OpenSearch RAG Example

Inbound voice agent that answers policyholder questions using **Amazon OpenSearch Service** with native Neural Search. `OpenSearchVectorStore` implements the `guava.helpers.rag.VectorStore` ABC.

Unlike the Elasticsearch example where embedding is done client-side, OpenSearch handles embedding, BM25, kNN search, and score fusion entirely server-side — `add_texts` just sends raw text.

## How it works

```
Caller asks a question
        │
        ▼
  Send raw query text
  (no client-side embedding)
        │
        ▼
┌─────────────────────────────────────────────┐
│  OpenSearchVectorStore(VectorStore)          │
│                                              │
│  "semantic" field type:                      │
│    auto-vectorizes text using hosted model   │
│                                              │
│  hybrid query:                               │
│    match (BM25) ────────────────────────┐    │
│    neural (kNN, auto-embedded) ─────────┤    │
│                                         │    │
│  Search Pipeline:                       │    │
│    normalization-processor ◄────────────┘    │
│    (min-max normalize + arithmetic mean)     │
│                                              │
│  ──► merged top-k chunks                     │
└──────────────────────────────────────────────┘
        │
        ▼
  DocumentQA.ask()
  (Gemini 2.5 Flash answers from chunks)
        │
        ▼
  Answer spoken to caller
```

Three OpenSearch-native features do the heavy lifting:

1. **Semantic field type** — `"semantic"` mapping auto-vectorizes text using a model deployed via ML Commons
2. **Hybrid query** — runs BM25 (`match`) and kNN (`neural`) search in parallel
3. **Search Pipeline** — normalizes and combines scores server-side

## Key differences from `elasticsearch_rag`

| | Elasticsearch | OpenSearch |
|---|---|---|
| Embedding | Vertex AI (client-side, 768-dim) | Server-side (hosted ML model) |
| Hybrid fusion | `sub_searches` + `rank` (RRF) | Search Pipeline (`normalization-processor`) |
| Field type | `text` + `dense_vector` (two fields) | `semantic` (one field, auto-vectorized) |
| Auth | Basic auth or API key | AWS SigV4 (IAM) |
| Hosting | Self-hosted or Elastic Cloud | AWS managed service |

## Documents

Policy knowledge is stored as plain text files in `docs/`. All `.txt` files are indexed on first run — OpenSearch generates embeddings automatically.

| File | Contents |
|------|----------|
| `policy_coverages.txt` | Coverages A–F, deductibles, exclusions |
| `endorsements_and_addons.txt` | Scheduled property, water backup, earthquake, flood, home business |
| `claims_process.txt` | Filing steps, timelines, dispute resolution, FAQ |
| `discounts_and_pricing.txt` | Rating factors, available discounts, premium calculation example |
| `cancellation_and_renewal.txt` | Cancellation, nonrenewal, reinstatement, payment options |

## Prerequisites

1. **OpenSearch domain** with kNN enabled
2. **Embedding model deployed** via [ML Commons](https://opensearch.org/docs/latest/ml-commons-plugin/pretrained-models/) or SageMaker — note the model ID
3. **AWS credentials** configured (env vars, IAM role, or AWS CLI profile)

## Running

```bash
export OPENSEARCH_ENDPOINT="https://search-my-domain-abc123.us-east-1.es.amazonaws.com"
export OPENSEARCH_MODEL_ID="your-deployed-model-id"

python -m examples.rag.hosted.opensearch_rag
```

Requires `GUAVA_API_KEY`, `GUAVA_AGENT_NUMBER`, `OPENSEARCH_ENDPOINT`, `OPENSEARCH_MODEL_ID`, and GCP credentials for Vertex AI (`GOOGLE_CLOUD_PROJECT`).

## Dependencies

- `opensearch-py` — OpenSearch Python client
- `requests-aws4auth` — AWS Signature Version 4 authentication
- `boto3` — AWS SDK for credential management
- `google-genai` — Gemini answer generation

## Key files

| File | Purpose |
|------|---------|
| `__main__.py` | `OpenSearchPolicyQAController` + `OpenSearchVectorStore(VectorStore)` — Search Pipeline setup, semantic index creation, hybrid query |
| `guava/helpers/rag/` | `DocumentQA`, `VectorStore` — SDK RAG helpers |

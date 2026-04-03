# Insurance Policy Q&A — DocumentQA Example

Inbound voice agent that answers policyholder questions using `DocumentQA` with the Guava server-side RAG API. Documents are uploaded to Guava at startup; incoming questions are answered by querying those documents via the server.

> **Note:** Server-side RAG is designed for testing and simple use cases. For larger document sets or more advanced retrieval, use a dedicated vector store (LanceDB, Pinecone, ChromaDB, or pgvector). Your documents are stored securely, but server-side RAG does not carry the data compliance guarantees available in the rest of Guava.

## How it works

```
Documents loaded from docs/
        │
        ▼
  DocumentQA(documents=DOCUMENTS)
        │    uploads to Guava server
        ▼
  Caller asks a question ──► DocumentQA.ask()
        │    server queries documents + generates answer via Gemini
        ▼
  Answer spoken to caller
```

## Documents

Policy knowledge is stored as plain text files in `docs/`. All `.txt` files are loaded and uploaded at startup.

| File | Contents |
|------|----------|
| `policy_coverages.txt` | Coverages A–F, deductibles, exclusions |
| `endorsements_and_addons.txt` | Scheduled property, water backup, earthquake, flood, home business |
| `claims_process.txt` | Filing steps, timelines, dispute resolution, FAQ |
| `discounts_and_pricing.txt` | Rating factors, available discounts, premium calculation example |
| `cancellation_and_renewal.txt` | Cancellation, nonrenewal, reinstatement, payment options |

## Running

```bash
export GUAVA_API_KEY=your_api_key
export GUAVA_AGENT_NUMBER=+15550001234
python -m examples.rag.basic_rag.document_qa
```

## Key files

| File | Purpose |
|------|---------|
| `__main__.py` | `PolicyQAController` — loads docs, creates `DocumentQA`, handles inbound calls |
| `docs/` | Plain-text policy documents uploaded to the server |

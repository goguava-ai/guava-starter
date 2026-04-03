# Salesforce Knowledge RAG Example

Inbound voice agent that answers questions from your **Salesforce Knowledge** base. Published Knowledge articles are fetched at startup via SOQL, stripped of HTML, and indexed into `DocumentQA` backed by `LanceDBStore`.


## How it works

```
Startup:
  Salesforce Knowledge__kav ──► SOQL query ──► strip HTML
          ──► DocumentQA (LanceDBStore)

Caller asks a question
        │
        ▼
┌──────────────────────────────────────┐
│  LanceDBStore (VectorStore)          │
│                                      │
│  Vertex AI embeds query    ────────┐ │
│                                    │ │
│  HNSW cosine similarity search ◄───┘ │
│  ──► matching article chunks         │
└──────────────────────────────────────┘
        │
        ▼
  DocumentQA.ask()
        │
        ▼
  Answer spoken to caller
```

## Running

```bash
export SALESFORCE_USERNAME="your@email.com"
export SALESFORCE_PASSWORD="yourpassword"
export SALESFORCE_SECURITY_TOKEN="yourtoken"

python -m examples.rag."examples of integrations".salesforce_knowledge_rag
```

Requires `GUAVA_API_KEY`, `GUAVA_AGENT_NUMBER`, and GCP credentials for Vertex AI (`GOOGLE_CLOUD_PROJECT`).

On first run, articles are fetched from Salesforce, embedded, and stored in `lancedb_data/`. Subsequent runs skip re-ingestion if data already exists.

## Environment variables

| Variable | Description |
|---|---|
| `SALESFORCE_USERNAME` | Salesforce login username |
| `SALESFORCE_PASSWORD` | Salesforce login password |
| `SALESFORCE_SECURITY_TOKEN` | Salesforce API security token (from Settings > Security > Reset Security Token) |
| `GUAVA_API_KEY` | Guava platform API key |
| `GUAVA_AGENT_NUMBER` | Inbound phone number |
| `GOOGLE_CLOUD_PROJECT` | GCP project for Vertex AI |

## Article type field

The example queries `Answer__c`, which is the body field for the default Salesforce FAQ article type. If your org uses a different article type or field name, update the SOQL query in `__main__.py`:

```python
result = sf.query(
    "SELECT Title, Body__c FROM MyArticleType__kav "  # adjust as needed
    "WHERE PublishStatus = 'Online' AND Language = 'en_US'"
)
```

## Dependencies

- `simple-salesforce` — Salesforce REST + SOQL client
- `google-genai` — Vertex AI embedding (768-dim) and Gemini answer generation

## Key files

| File | Purpose |
|---|---|
| `__main__.py` | `SalesforceKnowledgeController` — fetches articles via SOQL, indexes into LanceDB |
| `guava/helpers/rag/` | `DocumentQA`, `LanceDBStore`, `VectorStore` — SDK RAG helpers |

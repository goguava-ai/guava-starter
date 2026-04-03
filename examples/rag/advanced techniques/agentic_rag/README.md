# Multi-Product Insurance Q&A — Agentic RAG Example

Inbound voice agent for **Keystone Insurance Group** that routes questions to the correct knowledge base (auto, home, or life insurance) using `IntentRecognizer`, then answers from the relevant `DocumentQA` instance.

## How it works

```
Caller asks a question
        │
        ▼
┌───────────────────────────────────────────┐
│  IntentRecognizer (router)                │
│  "What product is this question about?"   │
│         │                                 │
│    ┌────┼────────────┐                    │
│    ▼    ▼            ▼                    │
│  auto  home         life                  │
│  DocumentQA        DocumentQA             │
│  (LanceDBStore)    (LanceDBStore)         │
│         │                                 │
│         ▼                                 │
│    top chunks from selected store         │
└───────────────────────────────────────────┘
        │
        ▼
  Gemini 2.5 Flash generates answer
```

`IntentRecognizer` from `guava.helpers.genai` classifies each question against product-line descriptions (e.g. "collision, comprehensive, liability" for auto) and picks the best match. Each product line has its own `DocumentQA` + `LanceDBStore` so results are never cross-contaminated.

**Without agentic RAG**, all documents share one index and a question about "collision deductible" might return homeowners deductible chunks too. **With agentic RAG**, the router sends auto questions to the auto index only.

## Knowledge bases

```
docs/
├── auto/
│   ├── auto_coverages.txt    # Liability, collision, comprehensive, rental
│   └── auto_claims.txt       # Accident procedures, total loss, rental coverage
├── home/
│   ├── home_coverages.txt    # Dwelling, personal property, liability
│   └── home_endorsements.txt # Water backup, scheduled property, equipment breakdown
└── life/
    ├── term_life.txt         # 10/20/30 year terms, premiums by age
    └── whole_life.txt        # Cash value, policy loans, dividends
```

## Running

```bash
python -m examples.rag.local.agentic_rag
```

Requires `GUAVA_API_KEY`, `GUAVA_AGENT_NUMBER`, and GCP credentials for Vertex AI (`GOOGLE_CLOUD_PROJECT`).

## Demo script

Try these questions to see routing in action:

1. **"What does my auto collision coverage pay for?"** → routes to `auto` store
2. **"Is water backup covered on my homeowners policy?"** → routes to `home` store
3. **"How much would a $500,000 term life policy cost for a 35-year-old?"** → routes to `life` store
4. **"What's my deductible for a car accident?"** → routes to `auto` (not home)

Watch the logs to see routing decisions:
```
INFO: Routed to 'auto insurance'
INFO: Routed to 'life insurance'
```

## Dependencies

Included via `pip install 'gridspace-guava[lancedb]'`:

- `lancedb` — local vector database (one store per product line)
- `google-genai` — Vertex AI embedding, Gemini routing and answer generation

## Key files

| File | Purpose |
|------|---------|
| `__main__.py` | `MultiProductQAController` — routes via `IntentRecognizer`, answers from per-product `DocumentQA` + `LanceDBStore` |
| `guava/helpers/rag/` | `DocumentQA`, `LanceDBStore` — SDK RAG helpers |
| `guava/helpers/genai.py` | `IntentRecognizer` — LLM-based intent classification |

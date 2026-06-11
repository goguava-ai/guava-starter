# Google GenAI (Gemini) Integration

Plug a raw `google.genai.Client` into Guava callbacks. Use this pattern when you want full control over the Gemini model, prompt, schema, or features (multimodal, system instructions, tool use) that aren't exposed by the built-in Guava helpers.

## When to use this

- ✅ You want to use your own `GOOGLE_API_KEY` (or Vertex AI auth) and pay Google directly for the LLM calls.
- ✅ You need a specific model (e.g. `gemini-2.5-pro`), system instruction, or custom JSON schema.
- ❌ You just need intent classification or natural-language slot filtering — use [`guava.helpers.llm.IntentRecognizer`](../../../docs/sdk-reference.md) and friends instead. Those work with only a `GUAVA_API_KEY`.

## What this example shows

`__main__.py` is a small inbound restaurant agent that:

1. **Classifies intent in `on_action_requested`** by calling `client.models.generate_content(...)` with `response_mime_type=application/json` and a Pydantic-derived `response_json_schema` constraining the output to a `Literal` of valid intents.
2. **Filters available time slots in `on_search_query`** by sending the caller's natural-language query plus the slot list to Gemini and parsing back `(matching, fallback)` lists.

Both calls live inline in the callback — Guava doesn't wrap, proxy, or mediate them. You see exactly which model, prompt, and schema get sent.

## Setup

### 1. Install dependencies

```bash
pip install gridspace-guava google-genai pydantic
```

### 2. Set environment variables

For the Gemini API:

```bash
export GUAVA_API_KEY="..."
export GUAVA_AGENT_NUMBER="+1..."
export GOOGLE_API_KEY="..."
# Optional — defaults to gemini-2.5-flash-lite
export GEMINI_MODEL="gemini-2.5-flash-lite"
```

For Vertex AI, edit `__main__.py` to construct the client as
`genai.Client(vertexai=True, project="...", location="us-central1")`
and follow [Google Cloud auth setup](https://cloud.google.com/docs/authentication/application-default-credentials).

### 3. Run

```bash
python -m examples.integrations.genai
```

Then call your `GUAVA_AGENT_NUMBER`.

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_API_KEY` | Guava server API key |
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `GOOGLE_API_KEY` | Your Gemini API key (skip if using Vertex AI auth) |
| `GEMINI_MODEL` | Gemini model id (default: `gemini-2.5-flash-lite`) |

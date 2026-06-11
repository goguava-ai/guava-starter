# OpenAI Integration

Plug a raw `openai.OpenAI` client into Guava callbacks. Use this pattern when you want full control over the model, prompt, schema, or features (function calling, fine-tunes, vision) that aren't exposed by the built-in Guava helpers.

## When to use this

- ✅ You want to use your own `OPENAI_API_KEY` and pay OpenAI directly for the LLM calls.
- ✅ You need a specific model, system prompt, fine-tune, tool-calling pattern, or custom JSON schema.
- ❌ You just need intent classification or natural-language slot filtering — use the tools provided in [`guava.helpers.llm`](../../../docs/sdk-reference.md) instead. Those work with only a `GUAVA_API_KEY`.

## What this example shows

`__main__.py` is a small inbound restaurant agent that:

1. **Classifies intent in `on_action_requested`** by calling `client.responses.create(...)` with a Pydantic-derived JSON schema that constrains the output to a `Literal` of valid intents.
2. **Filters available time slots in `on_search_query`** by sending the caller's natural-language query plus the slot list to OpenAI and parsing back `(matching, fallback)` lists.

Both calls live inline in the callback — Guava doesn't wrap, proxy, or mediate them. You see exactly which model, prompt, and schema get sent.

## Setup

### 1. Install dependencies

```bash
pip install gridspace-guava openai pydantic
```

### 2. Set environment variables

```bash
export GUAVA_API_KEY="..."
export GUAVA_AGENT_NUMBER="+1..."
export OPENAI_API_KEY="..."
# Optional — defaults to gpt-5-mini
export OPENAI_MODEL="gpt-5-mini"
```

### 3. Run

```bash
python -m examples.integrations.openai
```

Then call your `GUAVA_AGENT_NUMBER`.

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_API_KEY` | Guava server API key |
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `OPENAI_API_KEY` | Your OpenAI API key |
| `OPENAI_MODEL` | OpenAI model id (default: `gpt-5-mini`) |

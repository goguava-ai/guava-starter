# Guava Starter

Guava is a voice agent platform for developers. This repo is a starting point for building, exploring, and demoing Guava voice agents.

## Getting started

1. **Install the SDK** (Python >= 3.10 required):

   ```bash
   pip install gridspace-guava --extra-index-url https://guava-pypi.gridspace.com
   ```

2. **Set your credentials**:

   ```bash
   export GUAVA_API_KEY="..."
   export GUAVA_AGENT_NUMBER="..."
   ```

3. **Run an example** to make sure everything works:

   ```bash
   python -m guava.examples.scheduling_outbound +1...  # your phone number
   ```

See [`docs/quickstart.md`](docs/quickstart.md) for the full setup guide.

## Repo structure

```
docs/           SDK reference, quickstart, and use case guides
examples/       65 working demos organized by vertical (healthcare, retail, etc.)
users/          Where you build your own demos
```

## Building your own demo

1. **Create your folder** under `users/`:

   ```
   users/acme_corp/
   ```

2. **Copy and fill out the PRD template**:

   ```bash
   cp users/prd.md users/acme_corp/prd.md
   ```

   Open it and follow the instructions — you can fill it out manually or with an AI assistant.

3. **Generate your demo** — share your completed PRD with Claude (or another AI coding assistant) and ask it to build a Python demo in your folder:

   ```
   users/acme_corp/
   ├── prd.md          # your spec
   └── __main__.py     # your generated demo
   ```

Browse `examples/` for patterns to reference or copy from. The more detail in your PRD, the better your output.

## Documentation

- [`docs/quickstart.md`](docs/quickstart.md) — installation, setup, running examples
- [`docs/sdk-reference.md`](docs/sdk-reference.md) — full SDK reference
- [`docs/use-cases.md`](docs/use-cases.md) — use case patterns and guidance

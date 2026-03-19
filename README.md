# Users

This directory is where you build your own Guava voice agent demos.

## Getting started

1. **Create your own folder** — name it after your company or project:
   ```
   users/acme_corp/
   ```

2. **Copy the PRD template** into your folder:
   ```
   cp users/prd.md users/acme_corp/prd.md
   ```

3. **Fill out the PRD** — either on your own or interactively with an AI coding assistant.
   Open `prd.md` and read the instructions at the top — it explains both paths.

4. **Build your demo** — once your PRD is filled out, share it with Claude (or another AI coding assistant) and ask it to build a Python demo in your folder. Your finished project will look something like:
   ```
   users/acme_corp/
   ├── prd.md          ← your filled-out spec
   └── __main__.py     ← your generated demo
   ```

## Examples for reference

The `/examples` directory contains 65 working demos organized by vertical — browse them for patterns to reference or copy from.

## Tips

- The more detail you add to your PRD, the better your generated demo will be.
- You don't need to fill out every section — required fields are clearly marked.
- If you're not sure what to put somewhere, leave it blank and let your AI assistant ask you follow-up questions.

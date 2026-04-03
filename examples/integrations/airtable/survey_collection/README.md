# Survey Collection

**Direction:** Inbound

An agent conducts a brief customer satisfaction survey over the phone, collecting a rating, open-ended feedback, and likelihood to recommend, then saves the response as a new record in an Airtable table.

## What it does

1. Collects name, overall rating (1–5), what went well, improvement suggestions, and NPS likelihood
2. Saves the response via `POST /v0/{baseId}/{tableName}` with a `Channel: Phone` and date stamp

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `AIRTABLE_API_KEY` | Airtable Personal Access Token |
| `AIRTABLE_BASE_ID` | Base ID (e.g., `appXXXXXXXXXXXXXX`) |
| `AIRTABLE_SURVEY_TABLE` | Table name for survey responses (default: `Survey Responses`) |

## Usage

```bash
python -m examples.integrations.airtable.survey_collection
```

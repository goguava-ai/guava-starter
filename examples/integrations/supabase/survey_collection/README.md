# Survey Collection

**Direction:** Inbound

An agent conducts a customer satisfaction survey over the phone, collecting name, email, satisfaction score (1–5), open-ended feedback, and an NPS score (0–10), then inserts the response into a Supabase table.

## What it does

1. Collects respondent name, email, satisfaction score, qualitative feedback, and NPS score
2. Inserts a new row via `POST /rest/v1/{survey_table}` with `channel: phone` and `submitted_at` timestamp
3. Uses `Prefer: return=representation` to confirm the saved record's ID

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `SUPABASE_URL` | Supabase project URL (e.g., `https://{ref}.supabase.co`) |
| `SUPABASE_SERVICE_ROLE_KEY` | Service role key (bypasses RLS) |
| `SUPABASE_SURVEY_TABLE` | Table name for responses (default: `survey_responses`) |

## Usage

```bash
python -m examples.integrations.supabase.survey_collection
```

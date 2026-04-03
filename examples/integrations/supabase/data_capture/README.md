# Data Capture

**Direction:** Inbound

An inbound lead calls in. The agent collects their name, email, phone, company, interest area, and timeline, then inserts a new row into a Supabase leads table via the PostgREST API.

## What it does

1. Collects full name, email, phone, company, interest, and timeline
2. Inserts a new record via `POST /rest/v1/{leads_table}` with `Prefer: return=representation`
3. Sets `source: inbound_phone`, `status: new`, and `created_at` timestamp automatically

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `SUPABASE_URL` | Supabase project URL (e.g., `https://{ref}.supabase.co`) |
| `SUPABASE_SERVICE_ROLE_KEY` | Service role key (bypasses RLS) |
| `SUPABASE_LEADS_TABLE` | Table name for leads (default: `leads`) |

## Usage

```bash
python -m examples.integrations.supabase.data_capture
```

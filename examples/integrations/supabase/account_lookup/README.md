# Account Lookup

**Direction:** Inbound

A customer calls to look up their account. The agent verifies their identity by email or phone number, queries Supabase via the PostgREST API, and reads back account status, plan, and member-since date.

## What it does

1. Collects email or phone number for identity verification
2. Queries via `GET /rest/v1/users?email=eq.{email}` or `?phone=eq.{phone}`
3. Reads back account name, status, plan, and creation date

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `SUPABASE_URL` | Supabase project URL (e.g., `https://{ref}.supabase.co`) |
| `SUPABASE_SERVICE_ROLE_KEY` | Service role key (bypasses RLS) |

## Usage

```bash
python -m examples.integrations.supabase.account_lookup
```

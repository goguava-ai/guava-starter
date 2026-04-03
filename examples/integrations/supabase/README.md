# Supabase Integration

Voice agents that integrate with the [Supabase REST API](https://supabase.com/docs/guides/api) (built on PostgREST) to look up accounts, check order or record status, capture caller data, and run surveys — for applications built on Supabase's managed PostgreSQL backend.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`account_lookup`](account_lookup/) | Inbound | Caller verifies their account details; agent queries the users table |
| [`order_status`](order_status/) | Inbound | Caller asks about an order; agent looks up the orders table by order number |
| [`data_capture`](data_capture/) | Inbound | Caller submits a support request or contact form entry; agent writes to Supabase |
| [`survey_collection`](survey_collection/) | Inbound | Conduct a satisfaction survey over the phone and write responses to a Supabase table |

## Authentication

All examples use the service role key for server-side access:

```python
headers = {
    "apikey": os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    "Authorization": f"Bearer {os.environ['SUPABASE_SERVICE_ROLE_KEY']}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}
```

Find your URL and keys at **Project Settings → API** in the Supabase dashboard. Use the **service role key** for server-side agents (bypasses Row Level Security). Use the **anon key** only if your RLS policies are configured to allow the operation.

## Base URL

```
https://{project_ref}.supabase.co/rest/v1
```

Set `SUPABASE_URL` to your project URL (e.g., `https://xyzabc.supabase.co`). The REST API is at `{SUPABASE_URL}/rest/v1`.

## Common Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `SUPABASE_URL` | Project URL (e.g., `https://xyzabc.supabase.co`) |
| `SUPABASE_SERVICE_ROLE_KEY` | Service role key (server-side only) |

## Query Format

Supabase REST uses PostgREST query parameters for filtering:

```python
# GET with filter
requests.get(f"{BASE_URL}/orders", headers=headers, params={"id": f"eq.{order_id}"})

# POST to insert
requests.post(f"{BASE_URL}/contacts", headers=headers, json={"name": "...", "email": "..."})

# PATCH to update
requests.patch(f"{BASE_URL}/orders", headers=headers,
               params={"id": f"eq.{order_id}"}, json={"status": "cancelled"})
```

## Usage

```bash
python -m examples.integrations.supabase.account_lookup
python -m examples.integrations.supabase.order_status
python -m examples.integrations.supabase.data_capture

```bash
python -m examples.integrations.supabase.survey_collection
```

## Supabase API Reference

- [REST API Overview](https://supabase.com/docs/guides/api)
- [PostgREST Docs](https://postgrest.org/en/stable/references/api.html)
- [Row Filters](https://supabase.com/docs/reference/javascript/using-filters)

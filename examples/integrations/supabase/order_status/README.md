# Order Status

**Direction:** Inbound

A customer calls to check the status of an order. The agent verifies their email, queries the Supabase orders table via PostgREST, and reads back status, total, shipping status, and tracking number.

## What it does

1. Collects customer email and optional order number
2. Queries via `GET /rest/v1/orders?order_number=eq.{num}` or joins with users table by email
3. Reads back order status, total, shipping status, and tracking number

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `SUPABASE_URL` | Supabase project URL (e.g., `https://{ref}.supabase.co`) |
| `SUPABASE_SERVICE_ROLE_KEY` | Service role key (bypasses RLS) |

## Usage

```bash
python -m examples.integrations.supabase.order_status
```

# Session Store

**Direction:** Inbound

Persists all data collected during a call to Redis with a configurable TTL, and publishes real-time Pub/Sub events so downstream systems can react immediately (e.g., a processing pipeline, a dashboard, or a webhook relay).

## What it does

1. Publishes a `call_started` event on call begin
2. Collects caller details and request information
3. Saves the full session as a JSON string to Redis (key: `call_session:{session_id}`)
4. Publishes a `call_completed` event with the full session payload

## Redis Keys & Channels

| Type | Key / Channel | TTL | Description |
|---|---|---|---|
| String | `call_session:{session_id}` | `SESSION_TTL_SECONDS` | Full session JSON |
| Pub/Sub | `call_events:{session_id}` | — | Real-time event stream |

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `REDIS_URL` | Redis connection URL |
| `SESSION_TTL_SECONDS` | How long to retain session data (default: `3600`) |

## Usage

```bash
python __main__.py
```

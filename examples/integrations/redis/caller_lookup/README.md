# Caller Lookup

**Direction:** Inbound

Recognizes returning callers by phone number using a Redis cache. Returning callers get a personalized greeting that references their last topic; new callers are greeted normally and their profile is saved for future calls.

## What it does

1. On call start, checks Redis for a cached profile keyed on `caller:{phone}`
2. If found: greets the caller by name and references their last topic
3. If not found: collects name and issue, then saves a profile to Redis (30-day TTL)
4. On call end, updates `call_count` and `last_topic` in the profile

## Redis Keys

| Key | Type | TTL | Description |
|---|---|---|---|
| `caller:{phone}` | String (JSON) | 30 days | Caller profile: name, last_topic, call_count |

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `REDIS_URL` | Redis connection URL |

## Usage

```bash
python __main__.py
```

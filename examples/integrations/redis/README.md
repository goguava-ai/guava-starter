# Redis Integration

Voice agents that use [Redis](https://redis.io/) for caller profile caching, call deduplication, callback queue management, and real-time session storage — enabling stateful, personalized call experiences at scale.

## Examples

| Example | Direction | Description |
|---|---|---|
| [`caller_lookup`](caller_lookup/) | Inbound | Recognize returning callers by phone number, personalize the greeting, and update their cached profile |
| [`call_dedup`](call_dedup/) | Inbound | Detect repeat callers within a configurable window and handle them with elevated empathy or escalation |
| [`queue_callback`](queue_callback/) | Inbound | When agents are busy, add callers to a Redis list-based callback queue instead of holding |
| [`session_store`](session_store/) | Inbound | Persist all call-collected data to Redis with a TTL and publish real-time events via Pub/Sub |

## Authentication

All examples connect to Redis via a URL:

```python
r = redis.Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
```

Supports Redis Cloud, Upstash, ElastiCache, and self-hosted instances. TLS is handled automatically for `rediss://` URLs.

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `REDIS_URL` | Redis connection URL (e.g. `redis://localhost:6379` or `rediss://...`) |
| `DEDUP_WINDOW_SECONDS` | *(call_dedup only)* Repeat-caller cooldown window in seconds (default: 300) |
| `SESSION_TTL_SECONDS` | *(session_store only)* TTL for session data in seconds (default: 3600) |
| `CALLBACK_QUEUE_KEY` | *(queue_callback only)* Redis key for the callback queue list (default: `guava:callback_queue`) |

## Dependencies

```
pip install redis
```

# Queue Callback

**Direction:** Inbound

When agents are busy, offers callers a spot in a Redis list-based callback queue instead of holding. High-priority callers are pushed to the front of the queue (`LPUSH`); normal-priority callers go to the back (`RPUSH`).

## What it does

1. Offers the caller a callback option
2. If accepted: collects name, callback number, issue summary, and priority
3. High-priority callbacks are pushed to the front of the queue; normal to the back
4. Confirms their queue position and ends the call

## Redis Keys

| Key | Type | Description |
|---|---|---|
| `guava:callback_queue` (configurable) | List | Ordered list of JSON callback records |

## Consuming the Queue

A separate worker process pops from the queue and initiates outbound calls:

```python
import redis, json
r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
while True:
    record = r.lpop("guava:callback_queue")
    if record:
        data = json.loads(record)
        # initiate outbound call to data["phone"]
```

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `REDIS_URL` | Redis connection URL |
| `CALLBACK_QUEUE_KEY` | Redis list key (default: `guava:callback_queue`) |

## Usage

```bash
python __main__.py
```

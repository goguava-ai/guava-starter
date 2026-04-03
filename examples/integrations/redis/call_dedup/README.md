# Call Deduplication

**Direction:** Inbound

Detects when the same phone number calls multiple times within a configurable cooldown window. Repeat callers receive an elevated, empathetic response that acknowledges their repeat contact and offers to escalate.

## What it does

1. On call start, checks `recent_call:{phone}` in Redis (expires after `DEDUP_WINDOW_SECONDS`)
2. If key exists: the caller is flagged as a repeat — escalation path is offered
3. If not: normal call flow; key is set with the dedup window TTL
4. Lifetime call count is tracked separately in `call_count:{phone}`

## Redis Keys

| Key | Type | TTL | Description |
|---|---|---|---|
| `recent_call:{phone}` | String | `DEDUP_WINDOW_SECONDS` | Set if caller has called recently |
| `call_count:{phone}` | Integer | 1 year | Lifetime call count for this number |

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `REDIS_URL` | Redis connection URL |
| `DEDUP_WINDOW_SECONDS` | Repeat-caller cooldown in seconds (default: `300`) |

## Usage

```bash
python __main__.py
```

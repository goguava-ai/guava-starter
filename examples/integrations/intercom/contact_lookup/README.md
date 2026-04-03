# Contact Lookup

**Direction:** Inbound

Looks up a caller's Intercom contact profile by email before the support conversation begins. The agent greets them by name and uses their plan, activity, and session history as natural context.

## What it does

1. Asks for the caller's email address
2. Searches Intercom via `POST /contacts/search` (email match)
3. Extracts plan, last-seen date, session count, and unread conversation count
4. Uses the context to personalize the support experience

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `INTERCOM_ACCESS_TOKEN` | Intercom Access Token |

## Usage

```bash
python __main__.py
```

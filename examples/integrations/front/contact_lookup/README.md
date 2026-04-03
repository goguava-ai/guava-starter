# Contact Lookup

**Direction:** Inbound

Looks up a caller's Front contact record and their three most recent conversations before assisting them. The agent greets them by name and uses conversation history as context — without reading it aloud robotically.

## What it does

1. Asks for the caller's email address
2. Searches Front for a matching contact via `GET /contacts?q[handles][handle]={email}`
3. Fetches the contact's recent conversations via `GET /contacts/{id}/conversations`
4. Uses contact notes, groups, and conversation history to personalize the call

## Environment Variables

| Variable | Description |
|---|---|
| `GUAVA_AGENT_NUMBER` | Your Guava agent's phone number |
| `FRONT_API_TOKEN` | Front API token |

## Usage

```bash
python __main__.py
```
